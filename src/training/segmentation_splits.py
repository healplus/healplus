"""Deterministic patient-grouped folds balanced by multiclass mask content."""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .segmentation_audit import AuditSample
from .segmentation_review import MaskReviewError, read_indexed_mask
from .tissue_taxonomy import TissueTaxonomy


class SplitPreparationError(ValueError):
    """Raised when safe patient-grouped folds cannot be produced."""


@dataclass(slots=True)
class _GroupStatistics:
    patient_token: str
    sample_ids: list[str] = field(default_factory=list)
    lesion_tokens: set[str] = field(default_factory=set)
    class_pixels: np.ndarray | None = None
    class_images: np.ndarray | None = None


def _sample_class_statistics(
    sample: AuditSample,
    taxonomy: TissueTaxonomy,
) -> tuple[np.ndarray, np.ndarray]:
    if sample.mask_path is None or not sample.mask_path.is_file():
        raise SplitPreparationError(f"{sample.sample_id}: missing mask")
    try:
        mask = read_indexed_mask(sample.mask_path)
    except MaskReviewError as exc:
        raise SplitPreparationError(
            f"{sample.sample_id}: invalid indexed mask"
        ) from exc
    unexpected = set(np.unique(mask).tolist()) - set(taxonomy.allowed_mask_values)
    if unexpected:
        raise SplitPreparationError(
            f"{sample.sample_id}: mask values outside taxonomy"
        )
    pixels = np.array(
        [int((mask == value).sum()) for value in taxonomy.trainable_values],
        dtype=np.int64,
    )
    images = (pixels > 0).astype(np.int64)
    return pixels, images


def _fold_balance_score(
    fold_pixels: np.ndarray,
    fold_images: np.ndarray,
    fold_sample_counts: np.ndarray,
    *,
    candidate_fold: int,
    group: _GroupStatistics,
    global_pixels: np.ndarray,
    global_images: np.ndarray,
    total_samples: int,
) -> float:
    projected_pixels = fold_pixels.copy()
    projected_images = fold_images.copy()
    projected_counts = fold_sample_counts.copy()
    projected_pixels[candidate_fold] += group.class_pixels
    projected_images[candidate_fold] += group.class_images
    projected_counts[candidate_fold] += len(group.sample_ids)

    pixel_denominator = np.maximum(global_pixels, 1)
    image_denominator = np.maximum(global_images, 1)
    pixel_balance = float(
        np.std(projected_pixels / pixel_denominator[None, :], axis=0).mean()
    )
    image_balance = float(
        np.std(projected_images / image_denominator[None, :], axis=0).mean()
    )
    sample_balance = float(
        np.std(projected_counts / max(total_samples, 1))
    )
    return pixel_balance + image_balance + (0.25 * sample_balance)


def create_patient_grouped_folds(
    samples: list[AuditSample],
    taxonomy: TissueTaxonomy,
    *,
    n_splits: int = 5,
    seed: int = 42,
) -> dict[str, Any]:
    if n_splits < 2:
        raise SplitPreparationError("n_splits must be at least two")
    if not samples:
        raise SplitPreparationError("no samples were provided")
    if any(not sample.patient_token for sample in samples):
        raise SplitPreparationError("patient identifiers are required for every sample")
    if any(not sample.lesion_token for sample in samples):
        raise SplitPreparationError("lesion identifiers are required for every sample")

    groups: dict[str, _GroupStatistics] = {}
    sample_lookup = {sample.sample_id: sample for sample in samples}
    for sample in samples:
        pixels, images = _sample_class_statistics(sample, taxonomy)
        group = groups.setdefault(
            sample.patient_token,
            _GroupStatistics(
                patient_token=sample.patient_token,
                class_pixels=np.zeros(taxonomy.num_classes, dtype=np.int64),
                class_images=np.zeros(taxonomy.num_classes, dtype=np.int64),
            ),
        )
        group.sample_ids.append(sample.sample_id)
        group.lesion_tokens.add(sample.lesion_token)
        group.class_pixels += pixels
        group.class_images += images

    if len(groups) < n_splits:
        raise SplitPreparationError(
            f"at least {n_splits} patient groups are required; found {len(groups)}"
        )

    global_pixels = sum(
        (group.class_pixels for group in groups.values()),
        start=np.zeros(taxonomy.num_classes, dtype=np.int64),
    )
    global_images = sum(
        (group.class_images for group in groups.values()),
        start=np.zeros(taxonomy.num_classes, dtype=np.int64),
    )
    missing_values = [
        value
        for value in taxonomy.trainable_values
        if global_pixels[value] == 0
    ]
    if missing_values:
        raise SplitPreparationError(
            "trainable classes have no pixels in the complete dataset"
        )

    rng = random.Random(seed)
    ordered_groups = list(groups.values())
    rng.shuffle(ordered_groups)

    def rarity_score(group: _GroupStatistics) -> tuple[float, int]:
        normalized_presence = group.class_images / np.maximum(global_images, 1)
        return float(normalized_presence[1:].sum()), len(group.sample_ids)

    ordered_groups.sort(key=rarity_score, reverse=True)
    fold_pixels = np.zeros((n_splits, taxonomy.num_classes), dtype=np.int64)
    fold_images = np.zeros((n_splits, taxonomy.num_classes), dtype=np.int64)
    fold_sample_counts = np.zeros(n_splits, dtype=np.int64)
    fold_groups: list[list[_GroupStatistics]] = [[] for _ in range(n_splits)]

    for group_index, group in enumerate(ordered_groups):
        if group_index < n_splits:
            chosen_fold = group_index
        else:
            scored_folds = [
                (
                    _fold_balance_score(
                        fold_pixels,
                        fold_images,
                        fold_sample_counts,
                        candidate_fold=fold_index,
                        group=group,
                        global_pixels=global_pixels,
                        global_images=global_images,
                        total_samples=len(samples),
                    ),
                    int(fold_sample_counts[fold_index]),
                    fold_index,
                )
                for fold_index in range(n_splits)
            ]
            chosen_fold = min(scored_folds)[2]
        fold_groups[chosen_fold].append(group)
        fold_pixels[chosen_fold] += group.class_pixels
        fold_images[chosen_fold] += group.class_images
        fold_sample_counts[chosen_fold] += len(group.sample_ids)

    assignments: list[dict[str, Any]] = []
    fold_summaries: dict[str, Any] = {}
    warnings: list[str] = []
    for fold_index, assigned_groups in enumerate(fold_groups):
        fold_name = f"fold_{fold_index}"
        lesion_tokens: set[str] = set()
        for group in assigned_groups:
            lesion_tokens.update(group.lesion_tokens)
            assignments.extend(
                {
                    "sample_id": sample_id,
                    "fold": fold_index,
                }
                for sample_id in group.sample_ids
            )
        missing_in_fold = [
            value
            for value in taxonomy.trainable_values
            if fold_pixels[fold_index, value] == 0
        ]
        if missing_in_fold:
            warnings.append(f"{fold_name}_missing_classes")
        fold_summaries[fold_name] = {
            "images": int(fold_sample_counts[fold_index]),
            "patient_groups": len(assigned_groups),
            "lesion_groups": len(lesion_tokens),
            "class_pixels": {
                str(value): int(fold_pixels[fold_index, value])
                for value in taxonomy.trainable_values
            },
            "class_images": {
                str(value): int(fold_images[fold_index, value])
                for value in taxonomy.trainable_values
            },
            "missing_class_values": missing_in_fold,
        }

    assignments.sort(key=lambda row: row["sample_id"])
    assigned_by_sample = {row["sample_id"]: row["fold"] for row in assignments}
    patient_folds: dict[str, set[int]] = defaultdict(set)
    lesion_folds: dict[str, set[int]] = defaultdict(set)
    for sample_id, fold_index in assigned_by_sample.items():
        sample = sample_lookup[sample_id]
        patient_folds[sample.patient_token].add(fold_index)
        lesion_folds[sample.lesion_token].add(fold_index)
    if any(len(folds) != 1 for folds in patient_folds.values()):
        raise SplitPreparationError("internal patient leakage detected")
    if any(len(folds) != 1 for folds in lesion_folds.values()):
        raise SplitPreparationError("a lesion appears under multiple patient groups")

    return {
        "schema_version": "1.0",
        "seed": seed,
        "n_splits": n_splits,
        "taxonomy_version": taxonomy.taxonomy_version,
        "privacy": {
            "raw_paths_in_report": False,
            "raw_group_identifiers_in_report": False,
        },
        "summary": {
            "images": len(samples),
            "patient_groups": len(groups),
            "lesion_groups": len(lesion_folds),
        },
        "folds": fold_summaries,
        "warnings": sorted(set(warnings)),
        "assignments": assignments,
    }


def write_grouped_fold_outputs(
    report: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, str]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "grouped_folds.json"
    csv_path = destination / "grouped_fold_assignments.csv"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "fold"])
        writer.writeheader()
        writer.writerows(report["assignments"])
    return {"json": str(json_path), "assignments_csv": str(csv_path)}
