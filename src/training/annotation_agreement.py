"""Inter-annotator agreement for pseudonymized indexed segmentation masks."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .segmentation_metrics import multiclass_confusion_matrix
from .segmentation_review import MaskReviewError, read_indexed_mask
from .tissue_taxonomy import TissueTaxonomy


@dataclass(frozen=True, slots=True)
class AnnotationPair:
    sample_id: str
    mask_a_path: Path
    mask_b_path: Path


def _safe_sample_id(value: str) -> str:
    return f"sample-{hashlib.sha256(value.encode()).hexdigest()[:16]}"


def _records_from_manifest(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    if path.suffix.lower() == ".jsonl":
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            rows = payload.get("pairs") or payload.get("samples") or payload.get("records")
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    raise ValueError("manifest must be CSV, JSONL, or JSON with pairs/samples/records")


def _resolve(root: Path, value: Any) -> Path:
    path = Path(str(value or "").strip())
    return path if path.is_absolute() else root / path


def load_annotation_pairs(
    manifest_path: str | Path,
    dataset_root: str | Path,
) -> list[AnnotationPair]:
    manifest = Path(manifest_path)
    root = Path(dataset_root).resolve()
    pairs: list[AnnotationPair] = []
    for index, record in enumerate(_records_from_manifest(manifest)):
        raw_a = record.get("mask_a") or record.get("annotator_a_mask")
        raw_b = record.get("mask_b") or record.get("annotator_b_mask")
        pair_key = str(record.get("sample_id") or record.get("id") or raw_a or index)
        pairs.append(
            AnnotationPair(
                sample_id=_safe_sample_id(pair_key),
                mask_a_path=_resolve(root, raw_a),
                mask_b_path=_resolve(root, raw_b),
            )
        )
    return pairs


def _dice_iou_from_confusion(confusion: np.ndarray) -> tuple[list[float | None], list[float | None]]:
    dice: list[float | None] = []
    iou: list[float | None] = []
    for class_index in range(confusion.shape[0]):
        true_positive = int(confusion[class_index, class_index])
        false_negative = int(confusion[class_index].sum() - true_positive)
        false_positive = int(confusion[:, class_index].sum() - true_positive)
        dice_denominator = (2 * true_positive) + false_positive + false_negative
        iou_denominator = true_positive + false_positive + false_negative
        dice.append(
            (2 * true_positive) / dice_denominator
            if dice_denominator
            else None
        )
        iou.append(
            true_positive / iou_denominator
            if iou_denominator
            else None
        )
    return dice, iou


def _cohen_kappa(confusion: np.ndarray) -> float | None:
    total = int(confusion.sum())
    if total == 0:
        return None
    observed = float(np.trace(confusion) / total)
    expected = float(
        np.dot(confusion.sum(axis=1), confusion.sum(axis=0)) / (total * total)
    )
    if np.isclose(expected, 1.0):
        return None
    return float((observed - expected) / (1.0 - expected))


def evaluate_annotation_agreement(
    pairs: list[AnnotationPair],
    taxonomy: TissueTaxonomy,
) -> dict[str, Any]:
    num_classes = taxonomy.num_classes
    aggregate_confusion = np.zeros((num_classes, num_classes), dtype=np.int64)
    rows: list[dict[str, Any]] = []
    blocker_counts: Counter[str] = Counter()
    valid_values = set(taxonomy.trainable_values)

    for pair in pairs:
        row: dict[str, Any] = {"sample_id": pair.sample_id}
        reasons: list[str] = []
        if not pair.mask_a_path.is_file():
            reasons.append("missing_mask_a")
        if not pair.mask_b_path.is_file():
            reasons.append("missing_mask_b")
        if reasons:
            blocker_counts.update(reasons)
            row.update(
                {
                    "status": "invalid",
                    "valid_pixels": 0,
                    "ignore_ratio": None,
                    "cohen_kappa": None,
                    "reason_codes": ",".join(reasons),
                }
            )
            rows.append(row)
            continue

        try:
            mask_a = read_indexed_mask(pair.mask_a_path)
            mask_b = read_indexed_mask(pair.mask_b_path)
        except MaskReviewError:
            blocker_counts["mask_decode_or_encoding_error"] += 1
            row.update(
                {
                    "status": "invalid",
                    "valid_pixels": 0,
                    "ignore_ratio": None,
                    "cohen_kappa": None,
                    "reason_codes": "mask_decode_or_encoding_error",
                }
            )
            rows.append(row)
            continue

        if mask_a.shape != mask_b.shape:
            blocker_counts["mask_size_mismatch"] += 1
            row.update(
                {
                    "status": "invalid",
                    "valid_pixels": 0,
                    "ignore_ratio": None,
                    "cohen_kappa": None,
                    "reason_codes": "mask_size_mismatch",
                }
            )
            rows.append(row)
            continue

        valid = (
            (mask_a != taxonomy.ignore_index)
            & (mask_b != taxonomy.ignore_index)
            & np.isin(mask_a, taxonomy.trainable_values)
            & np.isin(mask_b, taxonomy.trainable_values)
        )
        invalid_values = (
            (set(np.unique(mask_a).tolist()) | set(np.unique(mask_b).tolist()))
            - valid_values
            - {taxonomy.ignore_index}
        )
        if invalid_values:
            reasons.append("unexpected_mask_values")
            blocker_counts["unexpected_mask_values"] += 1

        pair_confusion = multiclass_confusion_matrix(
            mask_b[valid],
            mask_a[valid],
            num_classes=num_classes,
        )
        aggregate_confusion += pair_confusion
        pair_dice, _ = _dice_iou_from_confusion(pair_confusion)
        ignored = int(mask_a.size - valid.sum())
        row.update(
            {
                "status": "review" if reasons else "accepted",
                "valid_pixels": int(valid.sum()),
                "ignore_ratio": round(ignored / max(mask_a.size, 1), 6),
                "mean_present_class_dice": (
                    round(float(np.mean([value for value in pair_dice if value is not None])), 6)
                    if any(value is not None for value in pair_dice)
                    else None
                ),
                "cohen_kappa": (
                    round(kappa, 6)
                    if (kappa := _cohen_kappa(pair_confusion)) is not None
                    else None
                ),
                "reason_codes": ",".join(reasons),
            }
        )
        rows.append(row)

    dice, iou = _dice_iou_from_confusion(aggregate_confusion)
    class_metrics = {
        str(class_definition.value): {
            "key": class_definition.key,
            "dice": dice[class_definition.value],
            "iou": iou[class_definition.value],
            "support_pixels_annotator_a": int(
                aggregate_confusion[class_definition.value].sum()
            ),
            "support_pixels_annotator_b": int(
                aggregate_confusion[:, class_definition.value].sum()
            ),
        }
        for class_definition in taxonomy.trainable_classes
    }
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "privacy": {
            "raw_paths_in_report": False,
            "raw_identifiers_in_report": False,
            "clinical_previews_generated": False,
        },
        "taxonomy_version": taxonomy.taxonomy_version,
        "summary": {
            "pairs": len(pairs),
            "accepted_pairs": sum(row["status"] == "accepted" for row in rows),
            "review_pairs": sum(row["status"] == "review" for row in rows),
            "invalid_pairs": sum(row["status"] == "invalid" for row in rows),
            "valid_pixels": int(aggregate_confusion.sum()),
            "cohen_kappa": _cohen_kappa(aggregate_confusion),
        },
        "class_metrics": class_metrics,
        "pixel_confusion_matrix": aggregate_confusion.tolist(),
        "blockers": sorted(blocker_counts),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "samples": rows,
    }


def write_agreement_outputs(
    report: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, str]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "annotation_agreement.json"
    csv_path = destination / "annotation_agreement_samples.csv"
    markdown_path = destination / "annotation_agreement.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = [
        "sample_id",
        "status",
        "valid_pixels",
        "ignore_ratio",
        "mean_present_class_dice",
        "cohen_kappa",
        "reason_codes",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report["samples"])

    metric_rows = [
        (
            f"| `{value}` | {details['key']} | "
            f"{details['dice'] if details['dice'] is not None else 'N/A'} | "
            f"{details['iou'] if details['iou'] is not None else 'N/A'} |"
        )
        for value, details in report["class_metrics"].items()
    ]
    markdown_path.write_text(
        "\n".join(
            [
                "# Concordância entre anotadores",
                "",
                "Relatório agregado e pseudonimizado. Pixels 255 de qualquer anotador foram excluídos.",
                "",
                f"- Pares: {report['summary']['pairs']}",
                f"- Pares inválidos: {report['summary']['invalid_pairs']}",
                f"- Pixels válidos: {report['summary']['valid_pixels']}",
                f"- Cohen's Kappa agregado: {report['summary']['cohen_kappa']}",
                "",
                "| Classe | Nome | Dice | IoU |",
                "| --- | --- | ---: | ---: |",
                *metric_rows,
                "",
                "As métricas não substituem adjudicação clínica e devem ser interpretadas com as prevalências.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "json": str(json_path),
        "samples_csv": str(csv_path),
        "markdown": str(markdown_path),
    }
