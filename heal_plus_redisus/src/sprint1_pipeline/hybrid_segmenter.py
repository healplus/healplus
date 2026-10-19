"""Assistive neural tissue proposals with explicit abstention and CV explanations.

Colour, texture, geometric zones and professional clinical context form a
single neural input. No colour threshold assigns a tissue class. Heuristics
only flag acquisition artifacts and can increase uncertainty. The original
image, including skin pigmentation, is never whitened or recoloured.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Mapping, Protocol, Sequence

import cv2
import numpy as np
from numpy.typing import NDArray

from ..safety import ASSISTIVE_DISCLAIMER
from .roi_handler import ROI, ROIHandler, triad_zones, validate_rgb


TISSUE_CLASSES = ("granulacao", "esfacelo_fibrina", "necrose", "epitelizacao", "nao_classificado_baixa_confianca")
UNKNOWN_CLASS = 4
OUTSIDE_CLASS = 255
ETIOLOGIES = ("pressure", "venous", "arterial", "diabetic", "other", "unknown")
CONTEXT_FLAGS = ("suspected_blood", "residual_dressing", "recent_debridement")
FEATURE_NAMES = (
    "rgb_r",
    "rgb_g",
    "rgb_b",
    "hsv_h",
    "hsv_s",
    "hsv_v",
    "lab_l",
    "lab_a",
    "lab_b",
    "relative_lab_l",
    "relative_lab_a",
    "relative_lab_b",
    "texture_std",
    "texture_gradient",
    "texture_laplacian",
    "zone_core_proxy",
    "zone_border_proxy",
    "zone_perilesional_proxy",
    *(f"etiology_{name}" for name in ETIOLOGIES),
    *(f"context_{name}" for name in CONTEXT_FLAGS),
)


@dataclass(frozen=True)
class NeuralPrediction:
    probabilities: NDArray[np.float32]  # H×W×5 in the contextual crop's ORIGINAL coordinates
    bed_probability: NDArray[np.float32]  # independent H×W wound-contour probability


class NeuralBackend(Protocol):
    validated: bool
    model_version: str
    feature_names: tuple[str, ...]

    def predict(self, features: NDArray[np.float32]) -> NeuralPrediction: ...


@dataclass
class SegmentationResult:
    roi_id: str
    bbox: tuple[int, int, int, int]
    context_bbox: tuple[int, int, int, int]
    bed_mask: NDArray[np.bool_]
    class_map: NDArray[np.uint8]
    uncertainty: NDArray[np.float32]
    artifact_mask: NDArray[np.bool_]
    explanation_map: NDArray[np.float32]
    tissue_percentages: dict[str, float]
    tia_percent: float
    bed_uncertainty_percent: float
    percentages_scope: str
    status: str
    bed_source: str
    model_version: str | None = None
    feature_summary: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    disclaimer: str = ASSISTIVE_DISCLAIMER

    def to_dict(self) -> dict[str, Any]:
        """Minimized metrics/provenance; excludes pixels and clinical free text."""
        return {
            "roi_id": self.roi_id,
            "bbox": list(self.bbox),
            "context_bbox": list(self.context_bbox),
            "tissue_percentages": dict(self.tissue_percentages),
            "tia_percent": self.tia_percent,
            "review_required": self.tia_percent >= 25,
            "review_guidance": "Solicitar revisão humana ou nova captura antes de interpretar a composição."
            if self.tia_percent >= 25
            else "Interpretação clínica permanece sob responsabilidade profissional.",
            "bed_uncertainty_percent": self.bed_uncertainty_percent,
            "percentages_scope": self.percentages_scope,
            "status": self.status,
            "bed_source": self.bed_source,
            "model_version": self.model_version,
            "bed_area_pixels": int(self.bed_mask.sum()),
            "feature_summary": self.feature_summary,
            "warnings": list(self.warnings),
            "disclaimer": self.disclaimer,
        }


def merge_results(
    results: Sequence[SegmentationResult],
    shape: tuple[int, int],
) -> tuple[NDArray[np.bool_], NDArray[np.uint8], NDArray[np.float32]]:
    """Conservative union: overlapping uncertainty/disagreement remains unknown.

    Selecting only the most confident crop could hide an artifact visible in a
    neighbouring crop. No uncertain or conflicting overlap is promoted to a
    confident tissue class during aggregation.
    """
    bed = np.zeros(shape, bool)
    labels = np.full(shape, OUTSIDE_CLASS, np.uint8)
    uncertainty = np.zeros(shape, np.float32)
    for result in results:
        if result.class_map.shape != shape or result.bed_mask.shape != shape:
            raise ValueError("Every result must use the original image coordinates")
        support = result.class_map != OUTSIDE_CLASS
        overlap = support & (labels != OUTSIDE_CLASS)
        unresolved = overlap & (
            (labels != result.class_map) | (labels == UNKNOWN_CLASS) | (result.class_map == UNKNOWN_CLASS)
        )
        new_pixels = support & ~overlap
        labels[new_pixels] = result.class_map[new_pixels]
        uncertainty[support] = np.maximum(uncertainty[support], result.uncertainty[support])
        labels[unresolved] = UNKNOWN_CLASS
        uncertainty[unresolved] = np.maximum(uncertainty[unresolved], 0.65)
        artifacts = support & result.artifact_mask
        labels[artifacts] = UNKNOWN_CLASS
        uncertainty[artifacts] = 1
        bed |= result.bed_mask
    return bed, labels, uncertainty


def _validate_context(context: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(context, Mapping) or context.get("etiology") not in ETIOLOGIES:
        raise ValueError("Provide professional context with etiology (or explicitly 'unknown')")
    result: dict[str, Any] = {"etiology": context["etiology"]}
    for name in CONTEXT_FLAGS:
        value = context.get(name)
        if value is not None and type(value) is not bool:
            raise ValueError(f"Clinical context {name} must be boolean or unknown")
        result[name] = value
    return result


def extract_features(
    image: NDArray[np.uint8],
    bed_proxy: NDArray[np.bool_],
    context: Mapping[str, Any],
) -> tuple[NDArray[np.float32], dict[str, Any], NDArray[np.bool_]]:
    """Build the versioned 27-channel input without mapping colour to tissue.

    LAB offsets are relative to surrounding pixels, not an assumed universal
    light-skin value. The geometric proxy is explicitly unvalidated anatomy.
    Unknown clinical flags are encoded -1, preserving missingness.
    """
    context = _validate_context(context)
    rgb = image.astype(np.float32) / 255.0
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV).astype(np.float32) / np.array([179, 255, 255], np.float32)
    lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32) / 255.0
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    zones = triad_zones(bed_proxy)
    reference = zones.perilesional
    reference_available = bool(reference.any())
    baseline = np.median(lab[reference], axis=0) if reference_available else np.median(lab.reshape(-1, 3), axis=0)
    relative = lab - baseline
    mean = cv2.blur(gray, (7, 7))
    std = np.sqrt(np.maximum(cv2.blur(gray * gray, (7, 7)) - mean * mean, 0))
    gradient = cv2.magnitude(cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1))
    laplacian = np.abs(cv2.Laplacian(gray, cv2.CV_32F))
    texture = np.stack([std, np.minimum(gradient, 1), np.minimum(laplacian, 1)], axis=-1)
    zone_channels = np.stack([zones.bed, zones.border, zones.perilesional], axis=-1).astype(np.float32)
    values = [float(context["etiology"] == name) for name in ETIOLOGIES]
    values.extend(-1.0 if context[name] is None else float(context[name]) for name in CONTEXT_FLAGS)
    contextual = np.broadcast_to(np.asarray(values, np.float32), (*gray.shape, len(values)))
    features = np.concatenate([rgb, hsv, lab, relative, texture, zone_channels, contextual], axis=-1).astype(np.float32)

    # These are acquisition warnings, never a necrosis/granulation decision.
    reflection = (hsv[..., 2] > 0.985) & (hsv[..., 1] < 0.08)
    local_baseline = cv2.GaussianBlur(gray, (0, 0), 5)
    shadow = (gray < local_baseline * 0.45) & ((local_baseline - gray) > 0.08)
    local_lap_energy = cv2.blur(laplacian * laplacian, (9, 9))
    blur = local_lap_energy < 0.00008
    artifacts = reflection | shadow | blur
    if context["suspected_blood"] is True or context["residual_dressing"] is True:
        artifacts[:] = True
    summary = {
        "schema": "heal-hybrid-features-v1",
        "channels": len(FEATURE_NAMES),
        "relative_lab_baseline": [float(v) for v in baseline],
        "perilesional_reference_available": reference_available,
        "texture_std_mean": float(std.mean()),
        "zone_provenance": zones.provenance,
        "artifact_fraction": float(artifacts.mean()),
    }
    return features, summary, artifacts


class HybridSegmenter:
    def __init__(
        self,
        backend: NeuralBackend | None = None,
        confidence_threshold: float = 0.65,
        entropy_threshold: float = 0.65,
        context_margin: float = 0.25,
    ) -> None:
        if not all(math.isfinite(v) and 0 < v <= 1 for v in (confidence_threshold, entropy_threshold)):
            raise ValueError("Confidence and entropy thresholds must be in (0, 1]")
        self.backend = backend
        self.confidence_threshold = confidence_threshold
        self.entropy_threshold = entropy_threshold
        self.roi_handler = ROIHandler(context_margin)

    def segment(
        self,
        image_rgb: NDArray[np.uint8],
        roi: ROI,
        *,
        context: Mapping[str, Any],
        bed_mask: NDArray[np.bool_] | None = None,
        artifact_masks: Mapping[str, NDArray[np.bool_]] | None = None,
    ) -> SegmentationResult:
        """Segment one ROI and restore every map to the original image frame.

        Without approved weights, known bed pixels (or the unlocalized ROI)
        are all unknown. A provided bed must be a professional annotation;
        tissue uncertainty never supplies the wound-contour mask.
        """
        validate_rgb(image_rgb)
        roi.validate_shape(image_rgb.shape)
        clinical_context = _validate_context(context)
        original_shape = image_rgb.shape[:2]
        roi_mask = roi.mask(original_shape)
        if bed_mask is not None:
            if bed_mask.dtype != np.bool_ or bed_mask.shape != original_shape:
                raise ValueError("Professional bed mask must be boolean and match the original image")
            if np.any(bed_mask & ~roi_mask):
                raise ValueError("Professional bed extends beyond its assigned ROI")
        crop, context_bbox = self.roi_handler.crop(image_rgb, roi)
        x1, y1, x2, y2 = context_bbox
        source_proxy = roi_mask if bed_mask is None else bed_mask
        features, feature_summary, artifacts = extract_features(crop, source_proxy[y1:y2, x1:x2], clinical_context)
        for name, mask in (artifact_masks or {}).items():
            if name not in {"shadow", "reflection", "blood", "dressing", "blur", "other_reviewed_artifact"}:
                raise ValueError("Unsupported artifact annotation")
            if mask.dtype != np.bool_ or mask.shape != original_shape:
                raise ValueError("Artifact masks must be boolean in the original image coordinates")
            artifacts |= mask[y1:y2, x1:x2]

        labels = np.full(original_shape, OUTSIDE_CLASS, np.uint8)
        uncertainty = np.zeros(original_shape, np.float32)
        full_artifacts = np.zeros(original_shape, bool)
        full_artifacts[y1:y2, x1:x2] = artifacts
        explanation = np.zeros(original_shape, np.float32)
        explanation[y1:y2, x1:x2] = features[..., FEATURE_NAMES.index("texture_std")]
        backend = self.backend
        approved = backend is not None and backend.validated is True
        warnings = ["Geometric zones are explanatory proxies and require professional review."]
        if clinical_context["etiology"] == "unknown":
            warnings.append("Etiology is unknown; no etiological or staging inference is performed.")
        model_version = None
        if approved:
            assert backend is not None
            if tuple(backend.feature_names) != FEATURE_NAMES:
                raise ValueError("Checkpoint feature schema differs from this pipeline")
            model_version = backend.model_version
            prediction = backend.predict(features)
            probabilities = np.asarray(prediction.probabilities, dtype=np.float32)
            expected_shape = (*crop.shape[:2], len(TISSUE_CLASSES))
            bed_probability = np.asarray(prediction.bed_probability, dtype=np.float32)
            if probabilities.shape != expected_shape or bed_probability.shape != crop.shape[:2]:
                raise ValueError("Neural backend must return probabilities in original crop coordinates")
            if (
                not np.isfinite(probabilities).all()
                or not np.isfinite(bed_probability).all()
                or np.any(probabilities < 0)
                or np.any(probabilities > 1)
                or np.any(bed_probability < 0)
                or np.any(bed_probability > 1)
                or not np.allclose(probabilities.sum(axis=-1), 1, atol=0.001)
            ):
                raise ValueError("Neural backend returned invalid probabilities")
            if bed_mask is None:
                bed = np.zeros(original_shape, bool)
                bed[y1:y2, x1:x2] = bed_probability >= 0.5
                bed &= roi_mask
                bed_source = "neural_preliminary"
            else:
                bed, bed_source = bed_mask.copy(), "professional_annotation"
            entropy = -(probabilities * np.log(np.clip(probabilities, 1e-8, 1))).sum(axis=-1) / np.log(5)
            confidence = probabilities.max(axis=-1)
            local_labels = probabilities.argmax(axis=-1).astype(np.uint8)
            abstain = (
                (confidence < self.confidence_threshold)
                | (entropy >= self.entropy_threshold)
                | artifacts
                | (local_labels == UNKNOWN_CLASS)
            )
            # An uncertain contour is also insufficient support for a tissue claim.
            if bed_mask is None:
                abstain |= np.abs(bed_probability - 0.5) < 0.15
            local_labels[abstain] = UNKNOWN_CLASS
            local_uncertainty = np.maximum(np.maximum(entropy, 1 - confidence), probabilities[..., UNKNOWN_CLASS])
            local_uncertainty[abstain] = np.maximum(local_uncertainty[abstain], self.entropy_threshold)
            local_uncertainty[artifacts] = 1.0
            support = bed[y1:y2, x1:x2]
            labels[y1:y2, x1:x2][support] = local_labels[support]
            uncertainty[y1:y2, x1:x2][support] = local_uncertainty[support]
            status = "preliminary_assistive" if bed.any() else "abstained_no_visible_bed"
        else:
            bed = np.zeros(original_shape, bool) if bed_mask is None else bed_mask.copy()
            bed_source = "unavailable" if bed_mask is None else "professional_annotation"
            status = "abstained_no_validated_model"
            warnings.append("No validated checkpoint is available; no tissue or wound contour is inferred.")

        scope_mask = bed if bed.any() else roi_mask
        scope = "bed" if bed.any() else "unlocalized_roi"
        if not approved or not bed.any():
            labels[scope_mask] = UNKNOWN_CLASS
            uncertainty[scope_mask] = 1.0
        counts = [int(np.count_nonzero(labels[scope_mask] == i)) for i in range(5)]
        denominator = int(scope_mask.sum())
        percentages = {name: counts[i] * 100.0 / denominator for i, name in enumerate(TISSUE_CLASSES)}
        # Apply rounding residual to a nonempty class, preserving nonnegativity.
        largest_class = max(percentages, key=lambda name: percentages[name])
        percentages[largest_class] += 100.0 - sum(percentages.values())
        unknown_count = counts[UNKNOWN_CLASS]
        return SegmentationResult(
            roi.id,
            roi.bbox,
            context_bbox,
            bed,
            labels,
            uncertainty,
            full_artifacts,
            explanation,
            percentages,
            100.0 * unknown_count / int(roi_mask.sum()),
            100.0 * unknown_count / denominator,
            scope,
            status,
            bed_source,
            model_version,
            feature_summary,
            tuple(warnings),
        )

    def segment_many(
        self,
        image_rgb: NDArray[np.uint8],
        rois: list[ROI],
        *,
        context: Mapping[str, Any],
        bed_masks: Mapping[str, NDArray[np.bool_]] | None = None,
    ) -> list[SegmentationResult]:
        validated = self.roi_handler.validate(image_rgb, rois)
        return [
            self.segment(image_rgb, roi, context=context, bed_mask=(bed_masks or {}).get(roi.id)) for roi in validated
        ]
