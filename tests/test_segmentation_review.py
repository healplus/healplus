from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.training.segmentation_review import (
    MaskReviewError,
    colorize_indexed_mask,
    create_mask_overlay,
    write_review_decisions,
)
from src.training.tissue_taxonomy import load_tissue_taxonomy

TAXONOMY_PATH = Path(__file__).parents[1] / "ml" / "configs" / "tissue_taxonomy_v0.json"


def test_colorize_and_overlay_preserve_shape_and_ignore_color():
    taxonomy = load_tissue_taxonomy(TAXONOMY_PATH)
    image = np.full((2, 3, 3), 100, dtype=np.uint8)
    mask = np.array([[0, 1, 255], [2, 3, 0]], dtype=np.uint8)

    color_mask = colorize_indexed_mask(mask, taxonomy)
    overlay = create_mask_overlay(image, mask, taxonomy, alpha=0.5)

    assert color_mask.shape == image.shape
    assert tuple(color_mask[0, 2]) == taxonomy.ignore_color_rgb
    assert np.array_equal(overlay[0, 0], image[0, 0])
    assert not np.array_equal(overlay[0, 1], image[0, 1])


def test_overlay_rejects_mismatched_dimensions():
    taxonomy = load_tissue_taxonomy(TAXONOMY_PATH)

    with pytest.raises(MaskReviewError, match="same spatial size"):
        create_mask_overlay(
            np.zeros((4, 4, 3), dtype=np.uint8),
            np.zeros((3, 4), dtype=np.uint8),
            taxonomy,
        )


def test_review_decision_csv_contains_only_pseudonymous_fields(tmp_path):
    output = write_review_decisions(
        tmp_path / "review.csv",
        [
            {
                "sample_id": "sample-deadbeef",
                "review_status": "approved",
                "reason_code": "",
                "image_path": "private-patient-name.png",
            }
        ],
    )

    content = output.read_text(encoding="utf-8")
    assert "sample-deadbeef" in content
    assert "private-patient-name" not in content
