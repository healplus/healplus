from __future__ import annotations

import json

import cv2
import matplotlib
import numpy as np
import pytest
from PIL import Image

from src.training.guided_wound_annotation import (
    AnnotationWorkspace,
    GuidedAnnotationApp,
    GuidedAnnotationError,
    polygon_to_mask,
)

matplotlib.use("Agg")


def _write_image(path, color=(120, 80, 180)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (40, 30), color).save(path)


def test_polygon_mask_and_approval_are_resumable_without_source_names(tmp_path):
    source = tmp_path / "source"
    _write_image(source / "private-patient-10.jpg")
    _write_image(source / "private-patient-2.jpg", color=(20, 100, 140))
    workspace_path = tmp_path / "workspace"
    workspace = AnnotationWorkspace(source, workspace_path)
    item = workspace.items[0]
    mask = polygon_to_mask(
        (30, 40),
        [(5, 5), (25, 5), (25, 20), (5, 20)],
    )

    workspace.save_human_mask(
        item,
        mask,
        status="approved",
        provenance="human_manual",
    )

    assert workspace.approved_count == 1
    assert item.normalized_image_path.is_file()
    assert item.human_mask_path.is_file()
    progress = workspace.manifest_path.read_text(encoding="utf-8")
    assert "private-patient" not in progress
    assert str(source) not in progress
    assert json.loads(progress)["records"][0]["status"] == "approved"

    resumed = AnnotationWorkspace(source, workspace_path)
    assert resumed.approved_count == 1
    existing_only = AnnotationWorkspace.from_existing(workspace_path)
    assert existing_only.approved_count == 1
    assert existing_only.items[0].source_path == item.normalized_image_path


def test_exact_duplicate_images_are_only_presented_once(tmp_path):
    source = tmp_path / "source"
    _write_image(source / "one.png")
    (source / "two.png").write_bytes((source / "one.png").read_bytes())

    workspace = AnnotationWorkspace(source, tmp_path / "workspace")

    assert len(workspace.items) == 1


def test_pseudo_uncertain_pixels_are_not_prefilled_as_wound(tmp_path):
    source = tmp_path / "source"
    _write_image(source / "one.png")
    workspace = AnnotationWorkspace(source, tmp_path / "workspace")
    item = workspace.items[0]
    workspace.ensure_normalized_image(item)
    pseudo = np.zeros((30, 40), dtype=np.uint8)
    pseudo[:, :10] = 1
    pseudo[:, 10:20] = 255
    assert cv2.imwrite(str(item.pseudo_mask_path), pseudo)

    editable, origin = workspace.load_editable_mask(item)

    assert origin == "pseudo_suggestion"
    assert np.all(editable[:, :10] == 255)
    assert np.all(editable[:, 10:20] == 0)


def test_approval_rejects_empty_mask(tmp_path):
    source = tmp_path / "source"
    _write_image(source / "one.png")
    workspace = AnnotationWorkspace(source, tmp_path / "workspace")

    with pytest.raises(GuidedAnnotationError, match="cover"):
        workspace.save_human_mask(
            workspace.items[0],
            np.zeros((30, 40), dtype=np.uint8),
            status="approved",
            provenance="human_manual",
        )


def test_gui_lasso_approve_and_advance_smoke(tmp_path):
    source = tmp_path / "source"
    _write_image(source / "one.png")
    workspace = AnnotationWorkspace(source, tmp_path / "workspace")
    app = GuidedAnnotationApp(workspace, target_approved=1)

    app._on_lasso([(5, 5), (30, 5), (30, 24), (5, 24)])
    app._approve_next()

    assert app.completed
    assert workspace.approved_count == 1
