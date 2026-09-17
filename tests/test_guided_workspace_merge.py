from __future__ import annotations

import json

import numpy as np
from PIL import Image

from src.training.guided_workspace_merge import build_combined_workspace
from src.training.guided_wound_annotation import AnnotationWorkspace


def _write_image(path, color):
    image = np.zeros((24, 32, 3), dtype=np.uint8)
    image[:, :] = color
    Image.fromarray(image, mode="RGB").save(path)


def test_combined_workspace_preserves_groups_and_reviewed_masks(tmp_path):
    stage_1 = tmp_path / "stage_1"
    stage_2 = tmp_path / "stage_2"
    stage_1.mkdir()
    stage_2.mkdir()
    _write_image(stage_1 / "one.jpg", (120, 30, 20))
    _write_image(stage_1 / "shared.jpg", (50, 60, 70))
    _write_image(stage_1 / "shared-copy.jpg", (50, 60, 70))
    _write_image(stage_2 / "two.jpg", (20, 100, 40))
    _write_image(stage_2 / "shared.jpg", (50, 60, 70))

    reviewed_1 = AnnotationWorkspace(stage_1, tmp_path / "reviewed_1")
    mask = np.zeros((24, 32), dtype=np.uint8)
    mask[5:15, 8:20] = 255
    reviewed_1.save_human_mask(
        reviewed_1.items[0],
        mask,
        status="approved",
        provenance="human_manual",
    )
    reviewed_2 = AnnotationWorkspace(stage_2, tmp_path / "reviewed_2")
    reviewed_2.save_human_mask(
        reviewed_2.items[0],
        mask,
        status="approved",
        provenance="human_manual",
    )

    result = build_combined_workspace(
        {"stage_1": stage_1, "stage_2": stage_2},
        [reviewed_1.workspace_root, reviewed_2.workspace_root],
        tmp_path / "combined",
    )

    assert result["unique_images"] == 3
    assert result["approved_human_masks"] == 2
    assert result["duplicate_images_removed"] == 2
    combined = AnnotationWorkspace.from_existing(tmp_path / "combined")
    assert combined.approved_count == 2
    manifest = json.loads(combined.manifest_path.read_text(encoding="utf-8"))
    assert manifest["source_groups"] == ["stage_1", "stage_2"]
    assert all("source_path" not in record for record in manifest["records"])
