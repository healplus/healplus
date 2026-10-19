"""Auditable metrics and six-column assistive inspection panels."""

from __future__ import annotations

from collections import Counter
import csv
import json
from pathlib import Path
import textwrap
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from ..safety import ASSISTIVE_DISCLAIMER
from .cascade_evaluator import CascadeEvaluation, DetectionSample, EvaluationRecord, detection_map
from .hybrid_segmenter import TISSUE_CLASSES, merge_results
from .roi_handler import triad_zones, validate_rgb


METRIC_DEFINITIONS = {
    "dice": "2TP/(2TP+FP+FN); both masks empty: 1",
    "iou": "TP/(TP+FP+FN); both masks empty: 1",
    "sensitivity": "TP/(TP+FN); no reference positives: null",
    "specificity": "TN/(TN+FP); no reference negatives: null",
    "detector_iou": "sum Hungarian-matched box IoUs / max(reference count, predicted count); unmatched boxes score 0",
    "tia_percent": "100 * unknown pixels / reference ROI pixels; missed lesion ROI is unknown; overlaps counted once",
    "tissue_percentages": "within predicted bed only; if contour unavailable, 100% unknown with explicit abstention",
    "aggregate": "unweighted image-level macro means; no pooled clinical risk estimate",
    "category_E": "orthogonal uncertainty rejection flag at TIA >=35%; D is retained when D and E apply",
}


def aggregate_metrics(
    records: Sequence[EvaluationRecord],
    detection_samples: Sequence[DetectionSample] | None = None,
) -> dict[str, Any]:
    def macro(name: str) -> float | None:
        values = [getattr(record, name) for record in records if getattr(record, name) is not None]
        return float(np.mean(values)) if values else None

    names = (
        "dice_manual",
        "manual_iou",
        "manual_sensitivity",
        "manual_specificity",
        "detector_iou",
        "dice_cascade",
        "cascade_iou",
        "sensitivity",
        "specificity",
        "tia_percent",
    )
    return {
        "image_count": len(records),
        "macro_means": {name: macro(name) for name in names},
        "category_counts": dict(Counter(record.category for record in records)),
        "uncertainty_rejection_count": sum(record.uncertainty_rejection for record in records),
        "missed_lesions": sum(record.missed_lesions for record in records),
        "extra_detections": sum(record.extra_detections for record in records),
        "detection": detection_map(detection_samples)
        if detection_samples is not None
        else {"map_50_95": None, "reason": "Detection samples were not supplied"},
        "definitions": METRIC_DEFINITIONS,
        "disclaimer": ASSISTIVE_DISCLAIMER,
    }


def _safe_csv(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        value = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def export_metrics(
    records: Sequence[EvaluationRecord],
    output_dir: str | Path,
    *,
    detection_samples: Sequence[DetectionSample] | None = None,
) -> dict[str, Path]:
    """Persist minimized pseudonymous metrics, aggregates and Sprint 2 cases."""
    if len({record.image_id for record in records}) != len(records):
        raise ValueError("Image metrics must have unique pseudonymous identifiers")
    if detection_samples is not None and {item.image_id for item in detection_samples} != {
        record.image_id for record in records
    }:
        raise ValueError("Detection samples must exactly match the exported evaluation set")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rows = [record.to_dict() for record in records]
    paths = {
        name: output / filename
        for name, filename in {
            "json": "metrics.json",
            "csv": "metrics.csv",
            "aggregate": "aggregate.json",
            "critical": "sprint2_critical_cases.json",
        }.items()
    }
    paths["json"].write_text(
        json.dumps(
            {"records": rows, "disclaimer": ASSISTIVE_DISCLAIMER}, ensure_ascii=False, indent=2, allow_nan=False
        ),
        encoding="utf-8",
    )
    paths["aggregate"].write_text(
        json.dumps(aggregate_metrics(records, detection_samples), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    critical = [record.to_dict() for record in records if record.category in {"C", "D"} or record.uncertainty_rejection]
    paths["critical"].write_text(
        json.dumps(
            {"cases": critical, "disclaimer": ASSISTIVE_DISCLAIMER}, ensure_ascii=False, indent=2, allow_nan=False
        ),
        encoding="utf-8",
    )
    with paths["csv"].open("w", newline="", encoding="utf-8-sig") as handle:
        fieldnames = list(rows[0]) if rows else ["image_id", "disclaimer"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: _safe_csv(value) for name, value in row.items()})
    return paths


def save_inspection_panel(
    image_rgb: NDArray[np.uint8],
    evaluation: CascadeEvaluation,
    path: str | Path,
    *,
    reference_bed_mask: NDArray[np.bool_] | None = None,
) -> Path:
    """Render six columns; CV column contains features, never colour tissue rules.

    The input must have passed the upload/privacy gate. The footer contains
    the full official disclaimer in rendered text and PNG metadata.
    """
    validate_rgb(image_rgb)
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Rectangle

    shape = image_rgb.shape[:2]
    if reference_bed_mask is not None and (reference_bed_mask.shape != shape or reference_bed_mask.dtype != bool):
        raise ValueError("Reference bed mask must be boolean in original image coordinates")
    record = evaluation.record
    fig, axes = plt.subplots(1, 6, figsize=(25, 8.5))
    fig.subplots_adjust(left=0.015, right=0.985, bottom=0.39, top=0.84, wspace=0.12)
    titles = [
        "1 · Imagem sem metadados",
        "2 · ROI manual / detector",
        "3 · Textura + zonas (proxy)",
        "4 · Contorno proposto / referência",
        "5 · Incerteza por pixel",
        "6 · Proposta assistiva",
    ]
    for axis, title in zip(axes, titles, strict=True):
        axis.set_title(title, fontsize=11, pad=10)
        axis.axis("off")
    axes[0].imshow(image_rgb)
    axes[1].imshow(image_rgb)
    for rois, colour in ((evaluation.reference_rois, "#22c55e"), (evaluation.detected_rois, "#a855f7")):
        for roi in rois:
            x1, y1, x2, y2 = roi.bbox
            axes[1].add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False, edgecolor=colour, linewidth=2))
    axes[1].text(0, -0.08, "Verde: manual · Violeta: detector", transform=axes[1].transAxes, fontsize=9)
    selected = evaluation.cascade_results or evaluation.manual_results
    explanation = np.zeros(shape, np.float32)
    bed, classes, uncertainty = merge_results(selected, shape)
    for result in selected:
        explanation = np.maximum(explanation, result.explanation_map)
    if not evaluation.cascade_results:
        classes[:] = 255
        for roi in evaluation.reference_rois:
            roi_pixels = roi.mask(shape)
            uncertainty[roi_pixels] = 1
            classes[roi_pixels] = 4
    axes[2].imshow(explanation, cmap="gray", vmin=0, vmax=max(float(explanation.max(axis=None)), 0.01))
    proxy = bed.copy()
    if not proxy.any():
        for roi in evaluation.reference_rois:
            proxy |= roi.mask(shape)
    zones = triad_zones(proxy)
    for mask, colour in ((zones.border, "#00c8ff"), (zones.perilesional, "#ffd166")):
        if mask.any() and not mask.all():
            axes[2].contour(mask.astype(float), levels=[0.5], colors=[colour], linewidths=0.6)
    axes[2].text(0, -0.08, "CV explicável; sem classe por cor", transform=axes[2].transAxes, fontsize=9)
    axes[3].imshow(image_rgb)
    if bed.any() and not bed.all():
        axes[3].contour(bed.astype(float), levels=[0.5], colors=["#38bdf8"], linewidths=1.8)
    if reference_bed_mask is not None and reference_bed_mask.any() and not reference_bed_mask.all():
        axes[3].contour(reference_bed_mask.astype(float), levels=[0.5], colors=["#fbbf24"], linewidths=1.2)
    axes[3].text(0, -0.08, "Azul: proposta · Amarelo: referência", transform=axes[3].transAxes, fontsize=9)
    heatmap = axes[4].imshow(uncertainty, cmap="magma", vmin=0, vmax=1)
    colorbar = fig.colorbar(heatmap, ax=axes[4], fraction=0.04, pad=0.02)
    colorbar.ax.set_title("0–1", fontsize=8)
    axes[5].imshow(image_rgb)
    colour_map = ListedColormap(["#e76f51", "#e9c46a", "#64546b", "#f4b7cf", "#8c9aa8"])
    axes[5].imshow(
        np.ma.masked_where(classes == 255, classes),
        cmap=colour_map,
        vmin=0,
        vmax=4,
        alpha=0.55,
        interpolation="nearest",
    )
    axes[5].text(0, -0.08, "Cinza: não classificado", transform=axes[5].transAxes, fontsize=9)
    fig.suptitle(
        f"HEAL+ · revisão técnica {record.image_id} · categorias {' / '.join(record.categories)}", fontsize=15, y=0.95
    )
    metrics_line = f"Dice manual: {record.dice_manual:.3f}   |   IoU detector: {record.detector_iou:.3f}   |   Dice cascata: {record.dice_cascade:.3f}   |   TIA: {record.tia_percent:.1f}%"
    composition = "   ·   ".join(f"{name}: {record.tissue_percentages[name]:.1f}%" for name in TISSUE_CLASSES)
    statuses = ", ".join(sorted({result.status for result in evaluation.cascade_results})) or "abstained_no_detection"
    fig.text(0.02, 0.31, metrics_line, fontsize=11)
    fig.text(0.02, 0.265, composition, fontsize=10)
    fig.text(
        0.02,
        0.22,
        f"Estado: {statuses}. Zonas geométricas e percentuais exigem revisão profissional; fora do leito não é uma classe tecidual.",
        fontsize=9,
    )
    wrapped = textwrap.fill(ASSISTIVE_DISCLAIMER, width=185)
    fig.text(0.02, 0.06, wrapped, fontsize=10, linespacing=1.5, va="bottom")
    output = Path(path)
    if output.suffix.lower() != ".png":
        raise ValueError("Inspection panels must be saved as PNG")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=140, facecolor="white", metadata={"Description": ASSISTIVE_DISCLAIMER})
    plt.close(fig)
    return output


def export_experiment(
    evaluations: Sequence[CascadeEvaluation],
    images: Mapping[str, NDArray[np.uint8]],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Export the table/aggregates and automatically panel every B/C/D/E case."""
    records = [item.record for item in evaluations]
    samples = [
        DetectionSample(item.record.image_id, tuple(item.reference_rois), tuple(item.detected_rois))
        for item in evaluations
    ]
    paths = export_metrics(records, output_dir, detection_samples=samples)
    panels = []
    for evaluation in evaluations:
        if evaluation.record.category in {"B", "C", "D"} or evaluation.record.uncertainty_rejection:
            image_id = evaluation.record.image_id
            if image_id not in images:
                raise ValueError("An anonymized image is required for each critical inspection panel")
            panels.append(
                save_inspection_panel(images[image_id], evaluation, Path(output_dir) / "panels" / f"{image_id}.png")
            )
    return {**paths, "panels": panels}
