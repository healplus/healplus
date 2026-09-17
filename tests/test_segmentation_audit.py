from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np

from src.training.segmentation_audit import (
    DatasetAuditConfig,
    audit_segmentation_dataset,
    write_audit_outputs,
)
from src.training.tissue_taxonomy import load_tissue_taxonomy

TAXONOMY_PATH = Path(__file__).parents[1] / "ml" / "configs" / "tissue_taxonomy_v0.json"


def _write_image(path: Path, *, color: tuple[int, int, int] = (120, 80, 180)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.full((32, 40, 3), color, dtype=np.uint8)
    cv2.imwrite(str(path), image)


def _write_mask(path: Path, values: tuple[int, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mask = np.zeros((32, 40), dtype=np.uint8)
    width = max(mask.shape[1] // len(values), 1)
    for index, value in enumerate(values):
        mask[:, index * width : (index + 1) * width] = value
    cv2.imwrite(str(path), mask)


def test_audit_reports_pairing_duplicates_and_unexpected_values_without_raw_paths(tmp_path):
    _write_image(tmp_path / "images" / "private-name-a.png")
    _write_image(tmp_path / "images" / "private-name-b.png")
    _write_image(tmp_path / "images" / "orphan-image.png", color=(10, 20, 30))
    _write_mask(tmp_path / "masks" / "private-name-a.png", (0, 1, 2, 3, 255))
    _write_mask(tmp_path / "masks" / "private-name-b.png", (0, 1, 9))
    _write_mask(tmp_path / "masks" / "orphan-mask.png", (0, 1))
    taxonomy = load_tissue_taxonomy(TAXONOMY_PATH)

    report = audit_segmentation_dataset(DatasetAuditConfig(dataset_root=tmp_path), taxonomy)

    assert report["summary"]["images_discovered"] == 3
    assert report["summary"]["images_without_masks"] == 1
    assert report["summary"]["masks_without_images"] == 1
    assert len(report["duplicates"]["exact_duplicate_groups"]) == 1
    assert "unexpected_mask_values" in report["release_blockers"]
    assert "patient_group_identifiers_incomplete" in report["release_blockers"]
    serialized = json.dumps(report)
    assert "private-name" not in serialized
    assert str(tmp_path) not in serialized

    outputs = write_audit_outputs(report, tmp_path / "audit")
    assert Path(outputs["json"]).exists()
    assert Path(outputs["samples_csv"]).exists()
    assert Path(outputs["review_csv"]).exists()
    assert Path(outputs["markdown"]).exists()


def test_audit_blocks_patient_lesion_and_duplicate_leak_between_splits(tmp_path):
    _write_image(tmp_path / "images" / "first.png")
    _write_image(tmp_path / "images" / "second.png")
    _write_mask(tmp_path / "masks" / "first.png", (0, 1, 2, 3))
    _write_mask(tmp_path / "masks" / "second.png", (0, 1, 2, 3))
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["image", "mask", "patient_id", "lesion_id", "split"],
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "image": "images/first.png",
                    "mask": "masks/first.png",
                    "patient_id": "patient-secret",
                    "lesion_id": "lesion-secret",
                    "split": "train",
                },
                {
                    "image": "images/second.png",
                    "mask": "masks/second.png",
                    "patient_id": "patient-secret",
                    "lesion_id": "lesion-secret",
                    "split": "test",
                },
            ]
        )
    taxonomy = load_tissue_taxonomy(TAXONOMY_PATH)

    report = audit_segmentation_dataset(
        DatasetAuditConfig(dataset_root=tmp_path, manifest_path=manifest),
        taxonomy,
    )

    assert "patient_split_leak" in report["release_blockers"]
    assert "lesion_split_leak" in report["release_blockers"]
    assert "exact_duplicate_cross_split" in report["release_blockers"]
    serialized = json.dumps(report)
    assert "patient-secret" not in serialized
    assert "lesion-secret" not in serialized

