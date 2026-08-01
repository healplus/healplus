"""Independent image-level holdout validation for binary wound segmentation."""

from __future__ import annotations

import csv
import json
import os
import shutil
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from PIL import Image

from src.processing.wound_segmentation_dl import (
    SmallUNet,
    clean_binary_mask,
    letterbox_pil,
    undo_letterbox,
)

from .guided_wound_annotation import AnnotationItem, AnnotationWorkspace
from .segmentation_metrics import binary_dice_score, binary_iou_score


class BinaryWoundValidationError(ValueError):
    """Raised when a holdout experiment cannot be built safely."""


def _single_source_group(
    workspace: AnnotationWorkspace,
    item: AnnotationItem,
) -> str:
    groups = workspace.record(item.sample_id).get("source_groups", [])
    if not isinstance(groups, list) or len(groups) != 1:
        return "unknown"
    return str(groups[0])


def stratified_image_holdout(
    workspace: AnnotationWorkspace,
    *,
    validation_fraction: float = 0.20,
    seed: int = 42,
) -> dict[str, Any]:
    """Reserve coverage-distributed images within each source group."""

    if not 0.05 <= validation_fraction <= 0.50:
        raise BinaryWoundValidationError("validation_fraction must be between 0.05 and 0.50")
    grouped: dict[str, list[tuple[float, AnnotationItem]]] = defaultdict(list)
    for item in workspace.approved_items():
        mask = cv2.imread(str(item.human_mask_path), cv2.IMREAD_GRAYSCALE)
        if mask is None:
            raise BinaryWoundValidationError(f"{item.sample_id}: reviewed mask could not be decoded")
        coverage = float((mask > 0).mean())
        grouped[_single_source_group(workspace, item)].append((coverage, item))
    if not grouped:
        raise BinaryWoundValidationError("no approved masks are available")

    rng = np.random.default_rng(seed)
    validation_ids: set[str] = set()
    group_summary: dict[str, Any] = {}
    for group, candidates in sorted(grouped.items()):
        candidates.sort(key=lambda pair: (pair[0], pair[1].sample_id))
        validation_count = max(1, round(len(candidates) * validation_fraction))
        if len(candidates) - validation_count < 1:
            raise BinaryWoundValidationError(f"source group {group} is too small for a holdout")
        coverage_blocks = np.array_split(
            np.arange(len(candidates)),
            validation_count,
        )
        selected_indices = {int(block[int(rng.integers(0, len(block)))]) for block in coverage_blocks if len(block)}
        validation_ids.update(candidates[index][1].sample_id for index in selected_indices)
        group_summary[group] = {
            "total": len(candidates),
            "train": len(candidates) - len(selected_indices),
            "validation": len(selected_indices),
        }

    assignments = [
        {
            "sample_id": item.sample_id,
            "source_group": _single_source_group(workspace, item),
            "role": ("validation" if item.sample_id in validation_ids else "train"),
        }
        for item in workspace.approved_items()
    ]
    assignments.sort(key=lambda row: row["sample_id"])
    return {
        "schema_version": "1.0",
        "strategy": "source_stratified_image_level_holdout_by_mask_coverage",
        "validation_fraction": validation_fraction,
        "seed": seed,
        "patient_grouping_used": False,
        "lesion_grouping_used": False,
        "patient_or_lesion_identifiers_available": False,
        "groups": group_summary,
        "assignments": assignments,
        "limitations": [
            "patient_and_lesion_ids_are_unavailable",
            "same_patient_or_lesion_may_exist_across_train_and_validation",
            "validation_is_experimental_and_not_a_clinical_test_set",
        ],
    }


def stratified_train_validation_test_split(
    workspace: AnnotationWorkspace,
    *,
    validation_fraction: float = 0.15,
    test_fraction: float = 0.15,
    seed: int = 42,
) -> dict[str, Any]:
    """Create coverage-stratified image-level train, validation and test roles."""

    if not 0.05 <= validation_fraction <= 0.30:
        raise BinaryWoundValidationError("validation_fraction must be between 0.05 and 0.30")
    if not 0.05 <= test_fraction <= 0.30:
        raise BinaryWoundValidationError("test_fraction must be between 0.05 and 0.30")
    if validation_fraction + test_fraction > 0.50:
        raise BinaryWoundValidationError("validation and test fractions must sum to at most 0.50")

    grouped: dict[str, list[tuple[float, AnnotationItem]]] = defaultdict(list)
    for item in workspace.approved_items():
        mask = cv2.imread(str(item.human_mask_path), cv2.IMREAD_GRAYSCALE)
        if mask is None:
            raise BinaryWoundValidationError(f"{item.sample_id}: reviewed mask could not be decoded")
        grouped[_single_source_group(workspace, item)].append((float((mask > 0).mean()), item))
    if not grouped:
        raise BinaryWoundValidationError("no approved masks are available")

    rng = np.random.default_rng(seed)
    roles: dict[str, str] = {}
    group_summary: dict[str, Any] = {}
    for group, candidates in sorted(grouped.items()):
        candidates.sort(key=lambda pair: (pair[0], pair[1].sample_id))
        total = len(candidates)
        validation_count = max(1, round(total * validation_fraction))
        test_count = max(1, round(total * test_fraction))
        if total - validation_count - test_count < 2:
            raise BinaryWoundValidationError(f"source group {group} is too small for three roles")

        available_indices = list(range(total))

        def select_coverage_distributed(
            indices: list[int],
            count: int,
        ) -> set[int]:
            blocks = np.array_split(np.asarray(indices), count)
            return {int(block[int(rng.integers(0, len(block)))]) for block in blocks if len(block)}

        test_indices = select_coverage_distributed(
            available_indices,
            test_count,
        )
        remaining_indices = [index for index in available_indices if index not in test_indices]
        validation_indices = select_coverage_distributed(
            remaining_indices,
            validation_count,
        )
        for index, (_, item) in enumerate(candidates):
            if index in test_indices:
                roles[item.sample_id] = "test"
            elif index in validation_indices:
                roles[item.sample_id] = "validation"
            else:
                roles[item.sample_id] = "train"
        group_summary[group] = {
            "total": total,
            "train": total - validation_count - test_count,
            "validation": validation_count,
            "test": test_count,
        }

    assignments = [
        {
            "sample_id": item.sample_id,
            "source_group": _single_source_group(workspace, item),
            "role": roles[item.sample_id],
        }
        for item in workspace.approved_items()
    ]
    assignments.sort(key=lambda row: row["sample_id"])
    return {
        "schema_version": "1.0",
        "strategy": ("source_stratified_image_level_train_validation_test_by_mask_coverage"),
        "validation_fraction": validation_fraction,
        "test_fraction": test_fraction,
        "seed": seed,
        "patient_grouping_used": False,
        "lesion_grouping_used": False,
        "patient_or_lesion_identifiers_available": False,
        "groups": group_summary,
        "assignments": assignments,
        "limitations": [
            "patient_and_lesion_ids_are_unavailable",
            "same_patient_or_lesion_may_exist_across_roles",
            "test_is_image_level_and_not_external_clinical_validation",
        ],
    }


def clone_validation_workspace(
    source_root: str | Path,
    destination_root: str | Path,
) -> AnnotationWorkspace:
    """Create an isolated hard-linked copy and reset non-human labels."""

    source = AnnotationWorkspace.from_existing(source_root)
    destination = Path(destination_root).resolve()
    manifest_path = destination / "annotation_progress.json"
    if manifest_path.exists():
        raise BinaryWoundValidationError("validation workspace already exists")
    normalized_dir = destination / "normalized_images"
    human_dir = destination / "human_masks"
    pseudo_dir = destination / "pseudo_masks"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    human_dir.mkdir(parents=True, exist_ok=True)
    pseudo_dir.mkdir(parents=True, exist_ok=True)

    approved_ids = {item.sample_id for item in source.approved_items()}
    records: list[dict[str, Any]] = []

    def link_or_copy(source_path: Path, destination_path: Path) -> None:
        try:
            os.link(source_path, destination_path)
        except OSError:
            shutil.copy2(source_path, destination_path)

    for item in source.items:
        link_or_copy(
            item.normalized_image_path,
            normalized_dir / item.normalized_image_path.name,
        )
        source_record = source.record(item.sample_id)
        record = {
            "sample_id": item.sample_id,
            "image_sha256": item.image_sha256,
            "normalized_image": f"normalized_images/{item.sample_id}.png",
            "source_groups": source_record.get("source_groups", []),
            "status": "unlabeled",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if item.sample_id in approved_ids:
            link_or_copy(
                item.human_mask_path,
                human_dir / item.human_mask_path.name,
            )
            record.update(
                {
                    "human_mask": f"human_masks/{item.sample_id}.png",
                    "status": "approved",
                    "provenance": "human_reviewed_validation_clone",
                }
            )
        records.append(record)

    payload = {
        "schema_version": "1.0",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "privacy": {
            "raw_source_paths_stored": False,
            "raw_identifiers_stored": False,
            "normalized_images_have_exif": False,
        },
        "source_groups": sorted({group for record in records for group in record.get("source_groups", [])}),
        "records": records,
    }
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return AnnotationWorkspace.from_existing(destination)


def _bootstrap_interval(
    values: Sequence[float],
    *,
    seed: int,
    iterations: int = 2_000,
) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0:
        return {"lower_95": 0.0, "upper_95": 0.0}
    rng = np.random.default_rng(seed)
    sampled = rng.choice(
        array,
        size=(iterations, array.size),
        replace=True,
    ).mean(axis=1)
    return {
        "lower_95": float(np.quantile(sampled, 0.025)),
        "upper_95": float(np.quantile(sampled, 0.975)),
    }


def _summarize_rows(
    rows: Sequence[dict[str, Any]],
    *,
    seed: int,
) -> dict[str, Any]:
    if not rows:
        raise BinaryWoundValidationError("validation rows are empty")
    dice_values = [float(row["dice"]) for row in rows]
    iou_values = [float(row["iou"]) for row in rows]
    tp = sum(int(row["true_positive_pixels"]) for row in rows)
    fp = sum(int(row["false_positive_pixels"]) for row in rows)
    fn = sum(int(row["false_negative_pixels"]) for row in rows)
    tn = sum(int(row["true_negative_pixels"]) for row in rows)
    return {
        "images": len(rows),
        "macro_dice": float(np.mean(dice_values)),
        "macro_iou": float(np.mean(iou_values)),
        "median_dice": float(np.median(dice_values)),
        "median_iou": float(np.median(iou_values)),
        "dice_95_ci": _bootstrap_interval(dice_values, seed=seed),
        "iou_95_ci": _bootstrap_interval(iou_values, seed=seed + 1),
        "micro_dice": float((2 * tp) / max((2 * tp) + fp + fn, 1)),
        "micro_iou": float(tp / max(tp + fp + fn, 1)),
        "precision": float(tp / max(tp + fp, 1)),
        "recall": float(tp / max(tp + fn, 1)),
        "specificity": float(tn / max(tn + fp, 1)),
        "confusion_pixels": {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "true_negative": tn,
        },
    }


def evaluate_binary_checkpoint(
    workspace: AnnotationWorkspace,
    validation_ids: set[str],
    checkpoint_path: str | Path,
    output_dir: str | Path,
    *,
    threshold: float = 0.5,
    device_name: str = "auto",
    seed: int = 42,
) -> dict[str, Any]:
    """Evaluate a frozen checkpoint on reviewed holdout masks."""

    if not 0.0 < threshold < 1.0:
        raise BinaryWoundValidationError("threshold must be between zero and one")
    if device_name == "cuda" and not torch.cuda.is_available():
        raise BinaryWoundValidationError("CUDA was requested but is unavailable")
    device = torch.device(
        "cuda" if device_name == "cuda" or (device_name == "auto" and torch.cuda.is_available()) else "cpu"
    )
    checkpoint_file = Path(checkpoint_path)
    checkpoint = torch.load(
        checkpoint_file,
        map_location=device,
        weights_only=False,
    )
    model = SmallUNet(base_channels=int(checkpoint["base_channels"])).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    image_size = int(checkpoint["training_args"]["image_size"])

    destination = Path(output_dir)
    prediction_dir = destination / "prediction_masks"
    overlay_dir = destination / "overlays"
    prediction_dir.mkdir(parents=True, exist_ok=True)
    overlay_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    for item in workspace.approved_items():
        if item.sample_id not in validation_ids:
            continue
        with Image.open(item.normalized_image_path) as source:
            image = source.convert("RGB")
            prepared, metadata = letterbox_pil(
                image,
                image_size,
                resample=Image.Resampling.BILINEAR,
                fill=(0, 0, 0),
            )
            image_rgb = np.asarray(image)
        image_array = np.array(prepared, dtype=np.float32, copy=True) / 255.0
        tensor = torch.from_numpy(np.ascontiguousarray(image_array.transpose(2, 0, 1))).unsqueeze(0).to(device)
        with torch.inference_mode():
            prepared_probabilities = torch.sigmoid(model(tensor))[0, 0].cpu().numpy()
        probabilities = undo_letterbox(
            prepared_probabilities,
            metadata,
            interpolation=cv2.INTER_LINEAR,
        )
        prediction = clean_binary_mask((probabilities >= threshold).astype(np.uint8) * 255)
        truth_raw = cv2.imread(
            str(item.human_mask_path),
            cv2.IMREAD_GRAYSCALE,
        )
        if truth_raw is None or truth_raw.shape != prediction.shape:
            raise BinaryWoundValidationError(f"{item.sample_id}: validation mask is invalid")
        truth = truth_raw > 0
        predicted = prediction > 0
        tp = int(np.logical_and(predicted, truth).sum())
        fp = int(np.logical_and(predicted, ~truth).sum())
        fn = int(np.logical_and(~predicted, truth).sum())
        tn = int(np.logical_and(~predicted, ~truth).sum())
        group = _single_source_group(workspace, item)
        rows.append(
            {
                "sample_id": item.sample_id,
                "source_group": group,
                "dice": binary_dice_score(predicted, truth, eps=0.0),
                "iou": binary_iou_score(predicted, truth, eps=0.0),
                "true_positive_pixels": tp,
                "false_positive_pixels": fp,
                "false_negative_pixels": fn,
                "true_negative_pixels": tn,
            }
        )
        cv2.imwrite(
            str(prediction_dir / f"{item.sample_id}.png"),
            prediction,
        )
        overlay = image_rgb.astype(np.float32).copy()
        overlay[truth] = (0.55 * overlay[truth]) + np.array(
            [0, 180, 0],
            dtype=np.float32,
        ) * 0.45
        overlay[predicted] = (0.55 * overlay[predicted]) + np.array(
            [239, 68, 68],
            dtype=np.float32,
        ) * 0.45
        Image.fromarray(
            np.clip(overlay, 0, 255).astype(np.uint8),
            mode="RGB",
        ).save(overlay_dir / f"{item.sample_id}.png")

    rows.sort(key=lambda row: row["sample_id"])
    if len(rows) != len(validation_ids):
        raise BinaryWoundValidationError("not every validation sample was evaluated")
    grouped_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped_rows[str(row["source_group"])].append(row)
    metrics = {
        "schema_version": "1.0",
        "checkpoint": str(checkpoint_file),
        "checkpoint_epoch": int(checkpoint["epoch"]) + 1,
        "model_version": checkpoint["model_version"],
        "threshold": threshold,
        "postprocessing": "clean_binary_mask",
        "overall": _summarize_rows(rows, seed=seed),
        "by_source_group": {
            group: _summarize_rows(group_rows, seed=seed) for group, group_rows in sorted(grouped_rows.items())
        },
        "validation_used_for_training": False,
        "test_set_used": False,
        "clinical_status": "experimental_requires_professional_review",
        "predictions": str(prediction_dir),
        "overlays": str(overlay_dir),
    }
    destination.mkdir(parents=True, exist_ok=True)
    metrics_path = destination / "metrics.json"
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (destination / "per_image_metrics.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    metrics["metrics_file"] = str(metrics_path)
    metrics["per_image_metrics"] = str(destination / "per_image_metrics.csv")
    return metrics
