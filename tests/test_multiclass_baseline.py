from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import pytest
import torch

from src.training.multiclass_baseline import (
    MulticlassBaselineConfig,
    MulticlassBaselineError,
    MulticlassSegmentationLoss,
    MulticlassUNet,
    MulticlassWoundDataset,
    augment_image_and_mask,
    letterbox_image_and_mask,
    train_multiclass_baseline,
)
from src.training.segmentation_audit import AuditSample
from src.training.tissue_taxonomy import load_tissue_taxonomy

TAXONOMY_PATH = Path(__file__).parents[1] / "ml" / "configs" / "tissue_taxonomy_v0.json"


def _write_sample(tmp_path: Path, index: int) -> AuditSample:
    image_path = tmp_path / f"image-{index}.png"
    mask_path = tmp_path / f"mask-{index}.png"
    image = np.zeros((32, 40, 3), dtype=np.uint8)
    mask = np.zeros((32, 40), dtype=np.uint8)
    mask[:16, :20] = 1
    mask[:16, 20:] = 2
    mask[16:, :20] = 3
    mask[16:20, 20:24] = 255
    image[mask == 1] = (180, 40, 40)
    image[mask == 2] = (210, 180, 80)
    image[mask == 3] = (50, 50, 50)
    assert cv2.imwrite(str(image_path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
    assert cv2.imwrite(str(mask_path), mask)
    return AuditSample(
        sample_id=f"sample-{index}",
        image_path=image_path,
        mask_path=mask_path,
        patient_token=f"patient-{index}",
        lesion_token=f"lesion-{index}",
    )


def test_letterbox_and_augmentation_keep_mask_values_and_alignment():
    image = np.zeros((20, 40, 3), dtype=np.uint8)
    mask = np.zeros((20, 40), dtype=np.uint8)
    mask[:, :20] = 1
    image[:, :20] = (255, 0, 0)

    augmented_image, augmented_mask = augment_image_and_mask(
        image,
        mask,
        rng=np.random.default_rng(2),
    )
    boxed_image, boxed_mask = letterbox_image_and_mask(
        augmented_image,
        augmented_mask,
        size=64,
    )

    assert boxed_image.shape == (64, 64, 3)
    assert boxed_mask.shape == (64, 64)
    assert set(np.unique(boxed_mask).tolist()) <= {0, 1}
    assert boxed_image[boxed_mask == 1, 0].mean() > boxed_image[boxed_mask == 0, 0].mean()


def test_unet_shape_and_losses_ignore_255_without_nan():
    model = MulticlassUNet(num_classes=4, base_channels=4)
    inputs = torch.rand(2, 3, 32, 32)
    targets = torch.randint(0, 4, (2, 32, 32))
    targets[:, :4, :4] = 255
    logits = model(inputs)

    assert logits.shape == (2, 4, 32, 32)
    for loss_name in ("cross_entropy_dice", "focal_dice", "focal_tversky"):
        loss = MulticlassSegmentationLoss(
            num_classes=4,
            ignore_index=255,
            loss_name=loss_name,
        )(logits, targets)
        assert torch.isfinite(loss)

    all_ignored = torch.full((2, 32, 32), 255)
    loss = MulticlassSegmentationLoss(num_classes=4)(logits, all_ignored)
    assert float(loss.item()) == 0.0


def test_dataset_converts_grayscale_input_to_rgb_and_preserves_ignore(tmp_path):
    sample = _write_sample(tmp_path, 0)
    grayscale = np.full((32, 40), 120, dtype=np.uint8)
    assert cv2.imwrite(str(sample.image_path), grayscale)
    taxonomy = load_tissue_taxonomy(TAXONOMY_PATH)
    dataset = MulticlassWoundDataset(
        [sample],
        taxonomy,
        image_size=32,
        training=False,
    )

    image, mask = dataset[0]

    assert image.shape == (3, 32, 32)
    assert mask.shape == (32, 32)
    assert 255 in torch.unique(mask).tolist()


def test_training_is_blocked_for_provisional_taxonomy(tmp_path):
    taxonomy = load_tissue_taxonomy(TAXONOMY_PATH)
    sample_a = _write_sample(tmp_path, 1)
    sample_b = _write_sample(tmp_path, 2)

    with pytest.raises(MulticlassBaselineError, match="clinically validated"):
        train_multiclass_baseline(
            [sample_a],
            [sample_b],
            taxonomy,
            MulticlassBaselineConfig(
                image_size=32,
                base_channels=4,
                batch_size=1,
                epochs=2,
            ),
            output_dir=tmp_path / "outputs",
            device_name="cpu",
        )


def test_two_epoch_cpu_training_smoke_test_writes_best_and_last_checkpoints(tmp_path):
    taxonomy = replace(
        load_tissue_taxonomy(TAXONOMY_PATH),
        status="approved",
        clinically_validated=True,
    )
    training_samples = [_write_sample(tmp_path, index) for index in range(3)]
    validation_samples = [_write_sample(tmp_path, 9)]
    output_dir = tmp_path / "outputs"

    metadata = train_multiclass_baseline(
        training_samples,
        validation_samples,
        taxonomy,
        MulticlassBaselineConfig(
            image_size=32,
            base_channels=4,
            batch_size=1,
            epochs=2,
            early_stopping_patience=0,
            mixed_precision=False,
        ),
        output_dir=output_dir,
        device_name="cpu",
    )

    assert metadata["epochs_completed"] == 2
    assert metadata["test_set_used"] is False
    assert (output_dir / "best_multiclass_unet.pt").is_file()
    assert (output_dir / "last_multiclass_unet.pt").is_file()
    assert (output_dir / "training_metadata.json").is_file()
