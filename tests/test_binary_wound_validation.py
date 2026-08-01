from __future__ import annotations

import json

import numpy as np
from PIL import Image

from src.training.binary_wound_validation import (
    clone_validation_workspace,
    stratified_image_holdout,
    stratified_train_validation_test_split,
)
from src.training.guided_wound_annotation import AnnotationWorkspace


def _workspace_with_groups(tmp_path):
    source = tmp_path / "images"
    source.mkdir()
    for index in range(20):
        image = np.zeros((24, 32, 3), dtype=np.uint8)
        image[:, :] = (50 + index, 80, 120)
        Image.fromarray(image, mode="RGB").save(source / f"image-{index}.png")
    workspace = AnnotationWorkspace(source, tmp_path / "workspace")
    for index, item in enumerate(workspace.items):
        mask = np.zeros((24, 32), dtype=np.uint8)
        width = 4 + (index % 8)
        mask[5:18, 4 : 4 + width] = 255
        workspace.save_human_mask(
            item,
            mask,
            status="approved",
            provenance="human_manual",
        )
    manifest = json.loads(workspace.manifest_path.read_text(encoding="utf-8"))
    for index, record in enumerate(manifest["records"]):
        record["source_groups"] = ["stage_1" if index < 10 else "stage_2"]
    workspace.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return AnnotationWorkspace.from_existing(workspace.workspace_root)


def test_holdout_is_deterministic_stratified_and_clonable(tmp_path):
    workspace = _workspace_with_groups(tmp_path)

    first = stratified_image_holdout(
        workspace,
        validation_fraction=0.20,
        seed=7,
    )
    second = stratified_image_holdout(
        workspace,
        validation_fraction=0.20,
        seed=7,
    )

    assert first == second
    assert first["groups"]["stage_1"] == {
        "total": 10,
        "train": 8,
        "validation": 2,
    }
    assert first["groups"]["stage_2"] == {
        "total": 10,
        "train": 8,
        "validation": 2,
    }
    clone = clone_validation_workspace(
        workspace.workspace_root,
        tmp_path / "clone",
    )
    assert clone.approved_count == 20
    assert len(clone.items) == 20


def test_three_way_split_is_stratified_and_disjoint(tmp_path):
    workspace = _workspace_with_groups(tmp_path)

    split = stratified_train_validation_test_split(
        workspace,
        validation_fraction=0.20,
        test_fraction=0.20,
        seed=9,
    )

    roles = {
        role: {row["sample_id"] for row in split["assignments"] if row["role"] == role}
        for role in ("train", "validation", "test")
    }
    assert roles["train"].isdisjoint(roles["validation"])
    assert roles["train"].isdisjoint(roles["test"])
    assert roles["validation"].isdisjoint(roles["test"])
    assert {len(ids) for ids in roles.values()} == {4, 12}
    assert split["groups"]["stage_1"] == {
        "total": 10,
        "train": 6,
        "validation": 2,
        "test": 2,
    }
