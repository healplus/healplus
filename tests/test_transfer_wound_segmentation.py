from __future__ import annotations

import cv2
import numpy as np
import torch
from PIL import Image

from src.training.semi_supervised_wound import BinaryTrainingSample
from src.training.transfer_wound_segmentation import (
    LRASPPBinaryDataset,
    _new_model,
)


def test_lraspp_dataset_and_model_smoke(tmp_path):
    image = np.zeros((32, 40, 3), dtype=np.uint8)
    image[:, :] = (80, 120, 160)
    mask = np.zeros((32, 40), dtype=np.uint8)
    mask[8:24, 10:30] = 255
    image_path = tmp_path / "image.png"
    mask_path = tmp_path / "mask.png"
    Image.fromarray(image, mode="RGB").save(image_path)
    assert cv2.imwrite(str(mask_path), mask)
    sample = BinaryTrainingSample(
        sample_id="sample-smoke",
        image_path=image_path,
        mask_path=mask_path,
        source_type="human",
        training_weight=1.0,
    )
    dataset = LRASPPBinaryDataset(
        [sample],
        image_size=32,
        training=True,
        seed=5,
    )

    image_tensor, mask_tensor, weight = dataset[0]
    model = _new_model(pretraining="none")
    output = model(image_tensor.unsqueeze(0))["out"]

    assert image_tensor.shape == (3, 32, 32)
    assert mask_tensor.shape == (32, 32)
    assert weight.item() == 1.0
    assert output.shape == (1, 1, 32, 32)
    assert torch.isfinite(output).all()
