"""Trainable, dual-head U-Net and hash-pinned, weights-only inference adapter.

No checkpoint is distributed. Initialising this network is suitable for shape
tests/training only. The segmenter refuses tissue proposals until documented
checkpoint approval has been supplied. Approval is governance evidence, not a
claim of regulatory approval or proof of clinical effectiveness.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import math
from pathlib import Path
import pickle
import re

import numpy as np
from numpy.typing import NDArray
import torch
from torch import nn
from torch.nn import functional as F

from .hybrid_segmenter import FEATURE_NAMES, NeuralPrediction


class _Block(nn.Module):
    def __init__(self, input_channels: int, output_channels: int) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Conv2d(input_channels, output_channels, 3, padding=1),
            nn.GroupNorm(4, output_channels),
            nn.ReLU(),
            nn.Conv2d(output_channels, output_channels, 3, padding=1),
            nn.GroupNorm(4, output_channels),
            nn.ReLU(),
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.layers(value)


class TissueProposalUNet(nn.Module):
    """Independent five-class tissue and binary bed-contour heads."""

    def __init__(self, input_channels: int = len(FEATURE_NAMES), base_channels: int = 16) -> None:
        super().__init__()
        if input_channels != len(FEATURE_NAMES) or base_channels < 4 or base_channels % 4:
            raise ValueError("Use the complete feature schema and a base width divisible by four")
        self.down1 = _Block(input_channels, base_channels)
        self.down2 = _Block(base_channels, base_channels * 2)
        self.center = _Block(base_channels * 2, base_channels * 4)
        self.up2 = _Block(base_channels * 6, base_channels * 2)
        self.up1 = _Block(base_channels * 3, base_channels)
        self.tissue = nn.Conv2d(base_channels, 5, 1)
        self.bed = nn.Conv2d(base_channels, 1, 1)

    def forward(self, features: torch.Tensor) -> dict[str, torch.Tensor]:
        first = self.down1(features)
        second = self.down2(F.max_pool2d(first, 2))
        center = self.center(F.max_pool2d(second, 2))
        up_second = F.interpolate(center, size=second.shape[-2:], mode="bilinear", align_corners=False)
        second_output = self.up2(torch.cat([up_second, second], dim=1))
        up_first = F.interpolate(second_output, size=first.shape[-2:], mode="bilinear", align_corners=False)
        output = self.up1(torch.cat([up_first, first], dim=1))
        return {"tissue_logits": self.tissue(output), "bed_logits": self.bed(output)}


def joint_loss(
    prediction: dict[str, torch.Tensor],
    tissue_target: torch.Tensor,
    bed_target: torch.Tensor,
    class_weights: torch.Tensor | None = None,
    alpha: float = 0.7,
    beta: float = 0.3,
    gamma: float = 1.33,
) -> torch.Tensor:
    """Weighted CE + focal Tversky + contour BCE for an auditable training loop.

    ``255`` marks pixels outside tissue support; class 4 remains a genuine
    uncertainty annotation. Tissue/bed targets must be expert annotations.
    """
    if not (0 <= alpha <= 1 and 0 <= beta <= 1 and gamma > 0):
        raise ValueError("Invalid focal Tversky parameters")
    logits = prediction["tissue_logits"]
    valid = tissue_target != 255
    if torch.any(valid):
        ce = F.cross_entropy(logits, tissue_target.long(), weight=class_weights, ignore_index=255)
        probabilities = torch.softmax(logits, dim=1) * valid[:, None]
        target = F.one_hot(tissue_target.masked_fill(~valid, 0).long(), 5).permute(0, 3, 1, 2) * valid[:, None]
        tp = (probabilities * target).sum((0, 2, 3))
        fp = (probabilities * (1 - target) * valid[:, None]).sum((0, 2, 3))
        fn = ((1 - probabilities) * target).sum((0, 2, 3))
        focal = (1 - (tp + 1e-6) / (tp + alpha * fp + beta * fn + 1e-6)).pow(gamma).mean()
    else:
        ce = logits.sum() * 0
        focal = logits.sum() * 0
    return ce + focal + F.binary_cross_entropy_with_logits(prediction["bed_logits"].squeeze(1), bed_target.float())


@dataclass(frozen=True)
class CheckpointApproval:
    model_version: str
    dataset_split_sha256: str
    review_reference: str
    approved: bool = False

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", self.model_version):
            raise ValueError("Model version must be a non-sensitive safe identifier")
        if not re.fullmatch(r"[a-fA-F0-9]{64}", self.dataset_split_sha256):
            raise ValueError("Approval requires a frozen dataset split digest")
        if not re.fullmatch(r"[A-Za-z0-9._/-]{1,160}", self.review_reference):
            raise ValueError("Approval requires a non-sensitive review reference")


class TorchUNetBackend:
    feature_names = FEATURE_NAMES

    def __init__(
        self,
        model: TissueProposalUNet,
        *,
        approval: CheckpointApproval | None = None,
        checkpoint_sha256: str | None = None,
        max_side: int = 512,
    ) -> None:
        if not isinstance(max_side, int) or not 32 <= max_side <= 2048:
            raise ValueError("Maximum inference side must be between 32 and 2048")
        self.model = model.cpu().eval()
        # A directly constructed (possibly randomly initialised) model can
        # never become inference-approved merely by attaching metadata.
        self.validated = False
        self.model_version = approval.model_version if approval else "untrained_shape_test_only"
        self.checkpoint_sha256 = checkpoint_sha256
        self.max_side = max_side

    @classmethod
    def from_checkpoint(
        cls,
        path: str | Path,
        *,
        expected_sha256: str,
        approval: CheckpointApproval,
        base_channels: int = 16,
        max_side: int = 512,
    ) -> "TorchUNetBackend":
        """Load a pinned local checkpoint with PyTorch's restricted loader.

        Required payload keys: ``state_dict``, ``feature_names`` and
        ``model_version``. No pickle globals or arbitrary object loader is used.
        """
        if not re.fullmatch(r"[a-fA-F0-9]{64}", expected_sha256):
            raise ValueError("Expected SHA-256 must contain 64 hexadecimal characters")
        checkpoint_path = Path(path)
        if checkpoint_path.stat().st_size > 256 * 1024 * 1024:
            raise ValueError("Checkpoint exceeds the 256 MB inference limit")
        raw = checkpoint_path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest.lower() != expected_sha256.lower():
            raise ValueError("Checkpoint integrity verification failed")
        try:
            payload = torch.load(io.BytesIO(raw), map_location="cpu", weights_only=True)
            if not isinstance(payload, dict) or tuple(payload.get("feature_names", ())) != FEATURE_NAMES:
                raise ValueError("Checkpoint feature schema is missing or incompatible")
            if payload.get("model_version") != approval.model_version:
                raise ValueError("Checkpoint model version differs from the approval record")
            model = TissueProposalUNet(base_channels=base_channels)
            model.load_state_dict(payload["state_dict"], strict=True)
        except (RuntimeError, KeyError, TypeError, ValueError, EOFError, pickle.UnpicklingError) as exc:
            raise ValueError("Checkpoint is not a compatible restricted HEAL+ state dictionary") from exc
        backend = cls(model, approval=approval, checkpoint_sha256=digest, max_side=max_side)
        backend.validated = approval.approved is True
        return backend

    def predict(self, features: NDArray[np.float32]) -> NeuralPrediction:
        if not self.validated:
            raise ValueError("Inference requires a hash-pinned checkpoint and recorded approval")
        if features.ndim != 3 or features.shape[2] != len(FEATURE_NAMES) or not np.isfinite(features).all():
            raise ValueError("Invalid hybrid feature tensor")
        height, width = features.shape[:2]
        scale = min(1.0, self.max_side / max(height, width))
        target_height = max(16, math.ceil(height * scale / 4) * 4)
        target_width = max(16, math.ceil(width * scale / 4) * 4)
        tensor = torch.from_numpy(np.ascontiguousarray(features.transpose(2, 0, 1))).float().unsqueeze(0)
        tensor = F.interpolate(tensor, size=(target_height, target_width), mode="bilinear", align_corners=False)
        with torch.inference_mode():
            result = self.model(tensor)
            tissue_logits = F.interpolate(
                result["tissue_logits"], size=(height, width), mode="bilinear", align_corners=False
            )
            bed_logits = F.interpolate(result["bed_logits"], size=(height, width), mode="bilinear", align_corners=False)
            probabilities = tissue_logits.softmax(dim=1)[0].permute(1, 2, 0).numpy().copy()
            bed_probability = bed_logits.sigmoid()[0, 0].numpy().copy()
        return NeuralPrediction(probabilities, bed_probability)
