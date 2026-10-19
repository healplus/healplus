"""Leakage-free manual-ROI vs detector→segmenter experiments.

Reference contours are used only as labels. Missing and extra lesions are
penalised in both box matching and union-mask scores. Operational categories
are technical thresholds, never clinical staging. E is an independent flag.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
from typing import Any, Mapping, Protocol, Sequence, TypedDict

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import linear_sum_assignment

from ..safety import ASSISTIVE_DISCLAIMER
from .hybrid_segmenter import HybridSegmenter, SegmentationResult, TISSUE_CLASSES, merge_results
from .roi_handler import ROI, ROIHandler, triad_zones, validate_rgb


class Detector(Protocol):
    def detect(self, image_rgb: NDArray[np.uint8]) -> list[ROI]: ...


class YoloDetectorAdapter:
    """Adapter for an already loaded Ultralytics-compatible model.

    No weights are fetched, trained, or trusted implicitly. The caller must
    supply its reviewed detector, class IDs and provenance in the manifest.
    """

    def __init__(
        self,
        model: Any,
        *,
        allowed_class_ids: tuple[int, ...] = (0,),
        confidence_threshold: float = 0.25,
        checkpoint_sha256: str | None = None,
        model_version: str | None = None,
    ):
        if not math.isfinite(confidence_threshold) or not 0 <= confidence_threshold <= 1:
            raise ValueError("Invalid detector confidence threshold")
        if (checkpoint_sha256 is None) != (model_version is None):
            raise ValueError("Detector provenance requires checkpoint SHA-256 and model version together")
        if checkpoint_sha256 is not None and not re.fullmatch(r"[a-fA-F0-9]{64}", checkpoint_sha256):
            raise ValueError("Detector checkpoint SHA-256 must contain 64 hexadecimal characters")
        if model_version is not None and not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", model_version):
            raise ValueError("Detector model version must be a safe non-sensitive identifier")
        self.model = model
        self.allowed_class_ids = allowed_class_ids
        self.confidence_threshold = confidence_threshold
        # The caller already loaded/reviewed this model. These are upstream
        # provenance assertions; this adapter does not verify or fetch weights.
        self.checkpoint_sha256 = checkpoint_sha256.lower() if checkpoint_sha256 is not None else None
        self.model_version = model_version

    def detect(self, image_rgb: NDArray[np.uint8]) -> list[ROI]:
        validate_rgb(image_rgb)
        # Ultralytics ndarray input convention is BGR, whereas this package is RGB.
        outputs = self.model.predict(source=np.ascontiguousarray(image_rgb[..., ::-1]), verbose=False)
        if not outputs:
            return []
        boxes = outputs[0].boxes
        if boxes is None:
            return []
        xyxy = boxes.xyxy.detach().cpu().numpy()
        confidence = boxes.conf.detach().cpu().numpy()
        classes = boxes.cls.detach().cpu().numpy()
        result: list[ROI] = []
        for coordinates, score, class_id in zip(xyxy, confidence, classes, strict=True):
            if int(class_id) not in self.allowed_class_ids or float(score) < self.confidence_threshold:
                continue
            if not np.isfinite(coordinates).all():
                raise ValueError("Detector returned invalid coordinates")
            left, top, right, bottom = coordinates
            bbox = (
                max(0, min(image_rgb.shape[1], math.floor(left))),
                max(0, min(image_rgb.shape[0], math.floor(top))),
                max(0, min(image_rgb.shape[1], math.ceil(right))),
                max(0, min(image_rgb.shape[0], math.ceil(bottom))),
            )
            if bbox[2] > bbox[0] and bbox[3] > bbox[1]:
                result.append(ROI(f"det-{len(result) + 1}", bbox, float(score), "detector"))
        return sorted(result, key=lambda roi: roi.confidence, reverse=True)[:100]


def bbox_iou(first: ROI | tuple[int, int, int, int], second: ROI | tuple[int, int, int, int]) -> float:
    a, b = (first.bbox if isinstance(first, ROI) else first), (second.bbox if isinstance(second, ROI) else second)
    if len(a) != 4 or len(b) != 4 or a[2] <= a[0] or a[3] <= a[1] or b[2] <= b[0] or b[3] <= b[1]:
        raise ValueError("IoU boxes must have positive area")
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return float(intersection / union)


class MaskMetrics(TypedDict):
    dice: float
    iou: float
    sensitivity: float | None
    specificity: float | None
    tp: int
    fp: int
    fn: int
    tn: int


def mask_metrics(predicted: NDArray[np.bool_], reference: NDArray[np.bool_]) -> MaskMetrics:
    if predicted.shape != reference.shape or predicted.ndim != 2 or predicted.dtype != bool or reference.dtype != bool:
        raise ValueError("Metric masks must be boolean, two-dimensional and equally sized")
    tp, fp = int((predicted & reference).sum()), int((predicted & ~reference).sum())
    fn, tn = int((~predicted & reference).sum()), int((~predicted & ~reference).sum())
    return {
        "dice": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 1.0,
        "iou": tp / (tp + fp + fn) if tp + fp + fn else 1.0,
        "sensitivity": tp / (tp + fn) if tp + fn else None,
        "specificity": tn / (tn + fp) if tn + fp else None,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


@dataclass(frozen=True)
class BoxMatching:
    pairs: tuple[tuple[int, int, float], ...]
    missed_reference: tuple[int, ...]
    extra_predictions: tuple[int, ...]
    penalized_mean_iou: float


def match_rois(reference: Sequence[ROI], predicted: Sequence[ROI]) -> BoxMatching:
    if not reference or not predicted:
        return BoxMatching(
            (), tuple(range(len(reference))), tuple(range(len(predicted))), 0.0 if reference or predicted else 1.0
        )
    overlaps = np.asarray([[bbox_iou(a, b) for b in predicted] for a in reference])
    row_indices, column_indices = linear_sum_assignment(-overlaps)
    pairs = tuple(
        (int(row), int(column), float(overlaps[row, column]))
        for row, column in zip(row_indices, column_indices, strict=True)
        if overlaps[row, column] > 0
    )
    matched_ref, matched_pred = {pair[0] for pair in pairs}, {pair[1] for pair in pairs}
    return BoxMatching(
        pairs,
        tuple(i for i in range(len(reference)) if i not in matched_ref),
        tuple(i for i in range(len(predicted)) if i not in matched_pred),
        sum(pair[2] for pair in pairs) / max(len(reference), len(predicted)),
    )


@dataclass(frozen=True)
class DetectionSample:
    image_id: str
    reference: tuple[ROI, ...]
    predicted: tuple[ROI, ...]


def detection_map(samples: Sequence[DetectionSample]) -> dict[str, Any]:
    """Single-class AP@.50:.95, 101 recall points, 100 detections/image.

    Matching is confidence-ordered and one-to-one per image/threshold. This
    COCO-inspired metric omits area strata and crowd annotations and is not an
    official pycocotools result. Images with no reference still contribute FPs.
    """
    if len({sample.image_id for sample in samples}) != len(samples):
        raise ValueError("Detection samples must have unique image identifiers")
    truth_count = sum(len(sample.reference) for sample in samples)
    if not truth_count:
        return {
            "map_50_95": None,
            "ap50": None,
            "ap75": None,
            "reference_count": 0,
            "method": "101-point-single-class-no-area-strata",
        }
    references = {sample.image_id: sample.reference for sample in samples}
    predictions = [
        (sample.image_id, roi)
        for sample in samples
        for roi in sorted(sample.predicted, key=lambda x: x.confidence, reverse=True)[:100]
    ]
    predictions.sort(key=lambda pair: pair[1].confidence, reverse=True)
    ap_values: list[float] = []
    for threshold in np.arange(0.5, 0.951, 0.05):
        used: dict[str, set[int]] = {sample.image_id: set() for sample in samples}
        true_positive: list[float] = []
        for image_id, roi in predictions:
            available = [
                (i, bbox_iou(roi, truth)) for i, truth in enumerate(references[image_id]) if i not in used[image_id]
            ]
            best = max(available, key=lambda item: item[1]) if available else None
            accepted = best is not None and best[1] + 1e-10 >= threshold
            true_positive.append(float(accepted))
            if accepted and best is not None:
                used[image_id].add(best[0])
        if not predictions:
            ap_values.append(0.0)
            continue
        tp = np.cumsum(true_positive)
        fp = np.cumsum(1 - np.asarray(true_positive))
        recall, precision = tp / truth_count, tp / np.maximum(tp + fp, 1)
        ap_values.append(
            float(np.mean([max(precision[recall >= level], default=0.0) for level in np.linspace(0, 1, 101)]))
        )
    return {
        "map_50_95": float(np.mean(ap_values)),
        "ap50": ap_values[0],
        "ap75": ap_values[5],
        "reference_count": truth_count,
        "ap_by_threshold": {f"{0.5 + 0.05 * i:.2f}": value for i, value in enumerate(ap_values)},
        "method": "101-point-single-class-no-area-strata",
    }


def categorize_failure(
    manual_dice: float, detector_iou: float, cascade_dice: float, tia_percent: float, *, border_cut: bool = False
) -> tuple[str, bool]:
    values = (manual_dice, detector_iou, cascade_dice)
    if (
        any(not math.isfinite(value) or not 0 <= value <= 1 for value in values)
        or not math.isfinite(tia_percent)
        or not 0 <= tia_percent <= 100
    ):
        raise ValueError("Invalid category metrics")
    if manual_dice < 0.60 and detector_iou < 0.50 and cascade_dice < 0.60:
        category = "D"
    elif manual_dice >= 0.80 and (detector_iou < 0.50 or border_cut):
        category = "B"
    elif manual_dice < 0.60 and detector_iou >= 0.70:
        category = "C"
    elif manual_dice >= 0.80 and detector_iou >= 0.70 and cascade_dice >= 0.80 and tia_percent < 20:
        category = "A"
    else:
        # The source definitions leave intermediate scores unassigned.
        category = "INTERMEDIATE"
    return category, tia_percent >= 35


@dataclass
class EvaluationRecord:
    image_id: str
    dataset_name: str
    dataset_license: str
    roi_count: int
    detected_count: int
    dice_manual: float
    detector_iou: float
    dice_cascade: float
    cascade_iou: float
    sensitivity: float | None
    specificity: float | None
    tia_percent: float
    category: str
    uncertainty_rejection: bool
    missed_lesions: int
    extra_detections: int
    detector_confidence: float | None
    tissue_percentages: dict[str, float]
    tissue_metrics: dict[str, dict[str, Any]] = field(default_factory=dict)
    border_invasion_percent: float = 0.0
    perilesional_invasion_percent: float = 0.0
    disclaimer: str = ASSISTIVE_DISCLAIMER
    manual_iou: float | None = None
    manual_sensitivity: float | None = None
    manual_specificity: float | None = None

    @property
    def categories(self) -> tuple[str, ...]:
        return (self.category, "E") if self.uncertainty_rejection else (self.category,)

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict

        result = asdict(self)
        result["categories"] = list(self.categories)
        return result


@dataclass
class CascadeEvaluation:
    record: EvaluationRecord
    manual_results: list[SegmentationResult]
    cascade_results: list[SegmentationResult]
    detected_rois: list[ROI]
    reference_rois: list[ROI]


class CascadeEvaluator:
    def __init__(self, segmenter: HybridSegmenter, detector: Detector) -> None:
        self.segmenter, self.detector = segmenter, detector

    def evaluate(
        self,
        image_id: str,
        image_rgb: NDArray[np.uint8],
        reference_rois: list[ROI],
        reference_bed_masks: Mapping[str, NDArray[np.bool_]],
        *,
        context: Mapping[str, Any],
        professional_bed_masks: Mapping[str, NDArray[np.bool_]] | None = None,
        reference_tissue_maps: Mapping[str, NDArray[np.uint8]] | None = None,
        dataset_name: str = "unspecified",
        dataset_license: str = "unverified",
    ) -> CascadeEvaluation:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", image_id):
            raise ValueError("Use a pseudonymous image identifier")
        ROIHandler().validate(image_rgb, reference_rois)
        shape = image_rgb.shape[:2]
        truth = np.zeros(shape, bool)
        if set(reference_bed_masks) != {roi.id for roi in reference_rois}:
            raise ValueError("Each reference ROI must have exactly one expert bed annotation")
        for roi in reference_rois:
            mask = reference_bed_masks[roi.id]
            if mask.dtype != bool or mask.shape != shape or not mask.any() or np.any(mask & ~roi.mask(shape)):
                raise ValueError("Reference bed annotations must be nonempty and contained in their ROI")
            if np.any(truth & mask):
                raise ValueError("Reference lesion beds must not overlap")
            truth |= mask
        manual = self.segmenter.segment_many(
            image_rgb, reference_rois, context=context, bed_masks=professional_bed_masks
        )
        detected = list(self.detector.detect(image_rgb))
        if detected:
            ROIHandler().validate(image_rgb, detected)
        cascade = self.segmenter.segment_many(image_rgb, detected, context=context) if detected else []
        manual_union = np.zeros(shape, dtype=bool)
        for result in manual:
            manual_union |= result.bed_mask
        cascade_union, proposed, _ = merge_results(cascade, shape)
        manual_metrics, cascade_metrics = mask_metrics(manual_union, truth), mask_metrics(cascade_union, truth)
        matching = match_rois(reference_rois, detected)
        # A missed lesion or box amputating any annotated bed is explicit border loss.
        border_cut = bool(matching.missed_reference)
        for reference_index, prediction_index, _ in matching.pairs:
            border_cut |= bool(
                np.any(
                    reference_bed_masks[reference_rois[reference_index].id] & ~detected[prediction_index].mask(shape)
                )
            )
        roi_union = np.zeros(shape, dtype=bool)
        for roi in reference_rois:
            roi_union |= roi.mask(shape)
        unknown_union = proposed == 4
        covered_roi = np.zeros(shape, bool)
        for roi in detected:
            covered_roi |= roi.mask(shape)
        unknown_union |= roi_union & ~covered_roi
        for index in matching.missed_reference:
            unknown_union |= reference_rois[index].mask(shape)
        tia = 100 * int((unknown_union & roi_union).sum()) / int(roi_union.sum())
        if not cascade:
            tia = 100.0
        category, rejection = categorize_failure(
            float(manual_metrics["dice"]),
            matching.penalized_mean_iou,
            float(cascade_metrics["dice"]),
            tia,
            border_cut=border_cut,
        )
        zones = triad_zones(truth)
        false_positive = cascade_union & ~truth
        predicted_count = max(1, int(cascade_union.sum()))
        support = cascade_union
        counts = np.array([np.count_nonzero((proposed == index) & support) for index in range(5)], dtype=float)
        proportions = counts * 100 / counts.sum() if counts.sum() else np.array([0.0, 0.0, 0.0, 0.0, 100.0])
        percentages = dict(zip(TISSUE_CLASSES, proportions.tolist(), strict=True))
        tissue_metrics: dict[str, dict[str, Any]] = {}
        if reference_tissue_maps is not None:
            if set(reference_tissue_maps) != {roi.id for roi in reference_rois}:
                raise ValueError("Tissue annotations must cover every reference lesion")
            tissue_truth = np.full(shape, 255, np.uint8)
            for roi in reference_rois:
                tissue_map = reference_tissue_maps[roi.id]
                bed = reference_bed_masks[roi.id]
                if (
                    tissue_map.shape != shape
                    or tissue_map.dtype != np.uint8
                    or not np.isin(tissue_map[bed], np.arange(5)).all()
                ):
                    raise ValueError("Tissue reference must contain classes 0–4 inside each expert bed")
                tissue_truth[bed] = tissue_map[bed]
            for index, name in enumerate(TISSUE_CLASSES):
                tissue_metrics[name] = dict(mask_metrics((proposed == index) & truth, tissue_truth == index))
        record = EvaluationRecord(
            image_id,
            dataset_name,
            dataset_license,
            len(reference_rois),
            len(detected),
            float(manual_metrics["dice"]),
            matching.penalized_mean_iou,
            float(cascade_metrics["dice"]),
            float(cascade_metrics["iou"]),
            cascade_metrics["sensitivity"],
            cascade_metrics["specificity"],
            tia,
            category,
            rejection,
            len(matching.missed_reference),
            len(matching.extra_predictions),
            float(np.mean([roi.confidence for roi in detected])) if detected else None,
            percentages,
            tissue_metrics,
            100 * int((false_positive & zones.border).sum()) / predicted_count,
            100 * int((false_positive & zones.perilesional).sum()) / predicted_count,
            manual_iou=float(manual_metrics["iou"]),
            manual_sensitivity=manual_metrics["sensitivity"],
            manual_specificity=manual_metrics["specificity"],
        )
        return CascadeEvaluation(record, manual, cascade, detected, reference_rois)
