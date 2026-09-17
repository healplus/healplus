from __future__ import annotations

import json

import cv2
import numpy as np
import torch
from PIL import Image

from src.training.guided_wound_annotation import AnnotationWorkspace
from src.training.semi_supervised_wound import (
    SemiSupervisedWoundConfig,
    generate_pseudo_labels,
    human_training_samples,
    pseudo_training_samples,
    semi_supervised_binary_loss,
    train_binary_stage,
    write_augmentation_preview,
    write_pipeline_report,
)


def _create_workspace(tmp_path, *, approved: int, unlabeled: int):
    source = tmp_path / "source"
    source.mkdir()
    total = approved + unlabeled
    for index in range(total):
        image = np.zeros((32, 40, 3), dtype=np.uint8)
        image[:, :] = (40 + index, 90, 130)
        image[8:24, 10:30] = (170, 60, 60)
        Image.fromarray(image, mode="RGB").save(source / f"image-{index}.png")
    workspace = AnnotationWorkspace(source, tmp_path / "workspace")
    for item in workspace.items[:approved]:
        mask = np.zeros((32, 40), dtype=np.uint8)
        mask[8:24, 10:30] = 255
        workspace.save_human_mask(
            item,
            mask,
            status="approved",
            provenance="human_manual",
        )
    return workspace


def test_binary_loss_ignores_uncertain_pixels():
    logits = torch.zeros((2, 1, 8, 8), requires_grad=True)
    targets = torch.zeros((2, 8, 8), dtype=torch.long)
    targets[:, :2, :2] = 1
    targets[:, 2:4, 2:4] = 255
    weights = torch.tensor([1.0, 0.3])

    loss = semi_supervised_binary_loss(logits, targets, weights)
    loss.backward()

    assert torch.isfinite(loss)
    assert torch.all(logits.grad[:, :, 2:4, 2:4] == 0)


def test_teacher_pseudo_label_and_student_inputs_smoke(tmp_path):
    workspace = _create_workspace(tmp_path, approved=3, unlabeled=2)
    config = SemiSupervisedWoundConfig(
        minimum_human_masks=3,
        image_size=32,
        base_channels=4,
        batch_size=1,
        teacher_epochs=2,
        student_epochs=1,
        foreground_threshold=0.5001,
        background_threshold=0.4999,
        minimum_confident_pixel_ratio=0.0,
        minimum_foreground_ratio=0.0,
        maximum_foreground_ratio=1.0,
        mixed_precision=False,
    )
    teacher_path = tmp_path / "workspace" / "checkpoints" / "teacher.pt"

    teacher = train_binary_stage(
        human_training_samples(workspace),
        config,
        output_path=teacher_path,
        stage="teacher",
        epochs=2,
        device_name="cpu",
    )
    pseudo = generate_pseudo_labels(
        workspace,
        teacher_path,
        config,
        device_name="cpu",
    )

    assert teacher["epochs"] == 2
    assert teacher["validation_used"] is False
    assert teacher["test_set_used"] is False
    assert pseudo["unlabeled_images_processed"] == 2
    assert pseudo["accepted_pseudo_labels"] == 2
    pseudo_samples = pseudo_training_samples(
        workspace,
        pseudo_label_weight=config.pseudo_label_weight,
    )
    assert len(pseudo_samples) == 2
    for sample in pseudo_samples:
        mask = cv2.imread(str(sample.mask_path), cv2.IMREAD_GRAYSCALE)
        assert set(np.unique(mask).tolist()) <= {0, 1, 255}
        assert sample.training_weight == config.pseudo_label_weight

    student = train_binary_stage(
        [*human_training_samples(workspace), *pseudo_samples],
        config,
        output_path=tmp_path / "workspace" / "checkpoints" / "student.pt",
        stage="student",
        epochs=1,
        device_name="cpu",
        initial_checkpoint=teacher_path,
    )
    assert student["pseudo_samples"] == 2
    assert student["human_samples"] == 3

    queue = (workspace.workspace_root / "pseudo_label_review_queue.csv").read_text(encoding="utf-8")
    assert "image-" not in queue
    summary = json.loads((workspace.workspace_root / "pseudo_label_summary.json").read_text(encoding="utf-8"))
    assert summary["accepted_pseudo_labels"] == 2


def test_augmentation_preview_is_generated_locally(tmp_path):
    workspace = _create_workspace(tmp_path, approved=1, unlabeled=0)

    output = write_augmentation_preview(workspace, count=20, seed=7)

    assert output.is_file()
    assert output.parent == workspace.workspace_root


def test_pipeline_report_distinguishes_supervised_and_semi_supervised_students(
    tmp_path,
):
    workspace = _create_workspace(tmp_path, approved=1, unlabeled=0)
    config = SemiSupervisedWoundConfig(minimum_human_masks=1)
    preview = workspace.workspace_root / "preview.png"
    preview.write_bytes(b"preview")
    common = {
        "workspace": workspace,
        "config": config,
        "teacher_result": {"checkpoint": "teacher.pt"},
        "pseudo_result": {"accepted_pseudo_labels": 0},
        "augmentation_preview": preview,
    }

    supervised_path = write_pipeline_report(
        **common,
        student_result={"checkpoint": "student.pt", "pseudo_samples": 0},
    )
    supervised = json.loads(supervised_path.read_text(encoding="utf-8"))
    assert supervised["status"] == "human_reviewed_student_trained_no_accepted_pseudo_labels"

    semi_supervised_path = write_pipeline_report(
        **common,
        student_result={"checkpoint": "student.pt", "pseudo_samples": 2},
    )
    semi_supervised = json.loads(semi_supervised_path.read_text(encoding="utf-8"))
    assert semi_supervised["status"] == "semi_supervised_student_trained"
