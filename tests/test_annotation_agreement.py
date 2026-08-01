from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np

from src.training.annotation_agreement import (
    evaluate_annotation_agreement,
    load_annotation_pairs,
    write_agreement_outputs,
)
from src.training.tissue_taxonomy import load_tissue_taxonomy

TAXONOMY_PATH = Path(__file__).parents[1] / "ml" / "configs" / "tissue_taxonomy_v0.json"


def _write_mask(path: Path, values: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(path), values)


def test_agreement_ignores_255_and_does_not_report_raw_identifiers(tmp_path):
    mask_a = np.array([[0, 1, 2], [3, 255, 1]], dtype=np.uint8)
    mask_b = np.array([[0, 1, 3], [3, 2, 1]], dtype=np.uint8)
    _write_mask(tmp_path / "a" / "patient-secret.png", mask_a)
    _write_mask(tmp_path / "b" / "patient-secret.png", mask_b)
    manifest = tmp_path / "pairs.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "mask_a", "mask_b"])
        writer.writeheader()
        writer.writerow(
            {
                "sample_id": "patient-secret",
                "mask_a": "a/patient-secret.png",
                "mask_b": "b/patient-secret.png",
            }
        )

    taxonomy = load_tissue_taxonomy(TAXONOMY_PATH)
    pairs = load_annotation_pairs(manifest, tmp_path)
    report = evaluate_annotation_agreement(pairs, taxonomy)

    assert report["summary"]["valid_pixels"] == 5
    assert report["pixel_confusion_matrix"][2][3] == 1
    assert report["class_metrics"]["1"]["dice"] == 1.0
    serialized = json.dumps(report)
    assert "patient-secret" not in serialized

    outputs = write_agreement_outputs(report, tmp_path / "outputs")
    assert Path(outputs["json"]).exists()
    assert Path(outputs["samples_csv"]).exists()
    assert Path(outputs["markdown"]).exists()


def test_agreement_reports_size_mismatch_without_paths(tmp_path):
    _write_mask(tmp_path / "a.png", np.zeros((3, 3), dtype=np.uint8))
    _write_mask(tmp_path / "b.png", np.zeros((4, 3), dtype=np.uint8))
    manifest = tmp_path / "pairs.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "id": "private-id",
                    "mask_a": "a.png",
                    "mask_b": "b.png",
                }
            ]
        ),
        encoding="utf-8",
    )

    taxonomy = load_tissue_taxonomy(TAXONOMY_PATH)
    report = evaluate_annotation_agreement(
        load_annotation_pairs(manifest, tmp_path),
        taxonomy,
    )

    assert report["summary"]["invalid_pairs"] == 1
    assert "mask_size_mismatch" in report["blockers"]
    assert "private-id" not in json.dumps(report)
