from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.training.segmentation_audit import AuditSample
from src.training.segmentation_splits import (
    SplitPreparationError,
    create_patient_grouped_folds,
    write_grouped_fold_outputs,
)
from src.training.tissue_taxonomy import load_tissue_taxonomy

TAXONOMY_PATH = Path(__file__).parents[1] / "ml" / "configs" / "tissue_taxonomy_v0.json"


def _sample(tmp_path: Path, patient: int, lesion: int, view: int) -> AuditSample:
    mask_path = tmp_path / f"mask-{patient}-{lesion}-{view}.png"
    mask = np.zeros((16, 16), dtype=np.uint8)
    mask[:8, :8] = 1
    mask[:8, 8:] = 2
    mask[8:, :8] = 3
    assert cv2.imwrite(str(mask_path), mask)
    return AuditSample(
        sample_id=f"sample-{patient}-{lesion}-{view}",
        image_path=tmp_path / f"image-{patient}-{lesion}-{view}.png",
        mask_path=mask_path,
        patient_token=f"patient-token-{patient}",
        lesion_token=f"lesion-token-{lesion}",
    )


def test_patient_grouped_folds_have_no_patient_or_lesion_leak(tmp_path):
    samples = []
    for patient in range(6):
        samples.append(_sample(tmp_path, patient, patient, 0))
        samples.append(_sample(tmp_path, patient, patient, 1))
    taxonomy = load_tissue_taxonomy(TAXONOMY_PATH)

    report = create_patient_grouped_folds(
        samples,
        taxonomy,
        n_splits=3,
        seed=7,
    )

    fold_by_sample = {
        row["sample_id"]: row["fold"]
        for row in report["assignments"]
    }
    for patient in range(6):
        assert fold_by_sample[f"sample-{patient}-{patient}-0"] == fold_by_sample[
            f"sample-{patient}-{patient}-1"
        ]
    assert all(details["images"] > 0 for details in report["folds"].values())
    assert not report["warnings"]

    outputs = write_grouped_fold_outputs(report, tmp_path / "outputs")
    serialized = Path(outputs["json"]).read_text(encoding="utf-8")
    assert "patient-token" not in serialized
    assert json.loads(serialized)["seed"] == 7


def test_grouped_folds_require_patient_and_lesion_ids(tmp_path):
    taxonomy = load_tissue_taxonomy(TAXONOMY_PATH)
    sample = _sample(tmp_path, 1, 1, 0)
    sample_without_patient = AuditSample(
        sample_id=sample.sample_id,
        image_path=sample.image_path,
        mask_path=sample.mask_path,
        lesion_token=sample.lesion_token,
    )

    with pytest.raises(SplitPreparationError, match="patient identifiers"):
        create_patient_grouped_folds(
            [sample_without_patient],
            taxonomy,
            n_splits=2,
        )
