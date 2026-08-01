"""Reproducible compact U-Net baseline for multiclass wound-tissue research."""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image, ImageOps, UnidentifiedImageError
from torch.utils.data import DataLoader, Dataset

from .segmentation_audit import AuditSample
from .segmentation_metrics import (
    multiclass_confusion_matrix,
    per_class_dice,
    per_class_iou,
    per_class_precision,
    per_class_recall,
    per_class_specificity,
    weighted_dice,
)
from .segmentation_review import MaskReviewError, read_indexed_mask
from .tissue_taxonomy import TissueTaxonomy


class MulticlassBaselineError(ValueError):
    """Raised when baseline data or configuration is unsafe."""


@dataclass(frozen=True, slots=True)
class MulticlassBaselineConfig:
    image_size: int = 256
    base_channels: int = 16
    batch_size: int = 4
    epochs: int = 30
    learning_rate: float = 3e-4
    weight_decay: float = 1e-4
    loss_name: str = "cross_entropy_dice"
    dice_weight: float = 0.5
    gradient_accumulation_steps: int = 1
    gradient_clip_norm: float = 1.0
    early_stopping_patience: int = 8
    num_workers: int = 0
    seed: int = 42
    mixed_precision: bool = True
    deterministic: bool = True
    allow_vertical_flip: bool = False

    def validate(self) -> None:
        if self.image_size < 32 or self.image_size % 16:
            raise MulticlassBaselineError("image_size must be >= 32 and divisible by 16")
        if self.base_channels < 4:
            raise MulticlassBaselineError("base_channels must be at least four")
        if self.batch_size <= 0 or self.epochs <= 0:
            raise MulticlassBaselineError("batch_size and epochs must be positive")
        if self.gradient_accumulation_steps <= 0:
            raise MulticlassBaselineError("gradient_accumulation_steps must be positive")
        if self.loss_name not in {
            "cross_entropy_dice",
            "focal_dice",
            "focal_tversky",
        }:
            raise MulticlassBaselineError("unsupported loss_name")


def set_reproducible_seed(seed: int, *, deterministic: bool = True) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if deterministic:
        torch.use_deterministic_algorithms(True, warn_only=True)
        if hasattr(torch.backends, "cudnn"):
            torch.backends.cudnn.benchmark = False
            torch.backends.cudnn.deterministic = True


def letterbox_image_and_mask(
    image_rgb: np.ndarray,
    mask: np.ndarray,
    *,
    size: int,
) -> tuple[np.ndarray, np.ndarray]:
    if image_rgb.ndim != 3 or image_rgb.shape[2] != 3:
        raise MulticlassBaselineError("image must be RGB")
    if mask.ndim != 2 or image_rgb.shape[:2] != mask.shape:
        raise MulticlassBaselineError("image and mask must have equal H x W")
    if size <= 0:
        raise MulticlassBaselineError("size must be positive")

    height, width = mask.shape
    scale = min(size / width, size / height)
    resized_width = max(1, int(round(width * scale)))
    resized_height = max(1, int(round(height * scale)))
    image_interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    resized_image = cv2.resize(
        image_rgb,
        (resized_width, resized_height),
        interpolation=image_interpolation,
    )
    resized_mask = cv2.resize(
        mask,
        (resized_width, resized_height),
        interpolation=cv2.INTER_NEAREST,
    )
    left = (size - resized_width) // 2
    right = size - resized_width - left
    top = (size - resized_height) // 2
    bottom = size - resized_height - top
    padded_image = cv2.copyMakeBorder(
        resized_image,
        top,
        bottom,
        left,
        right,
        cv2.BORDER_CONSTANT,
        value=(0, 0, 0),
    )
    padded_mask = cv2.copyMakeBorder(
        resized_mask,
        top,
        bottom,
        left,
        right,
        cv2.BORDER_CONSTANT,
        value=0,
    )
    return padded_image, padded_mask


def augment_image_and_mask(
    image_rgb: np.ndarray,
    mask: np.ndarray,
    *,
    rng: np.random.Generator,
    allow_vertical_flip: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    image = image_rgb.copy()
    target = mask.copy()
    if rng.random() < 0.5:
        image = np.fliplr(image).copy()
        target = np.fliplr(target).copy()
    if allow_vertical_flip and rng.random() < 0.3:
        image = np.flipud(image).copy()
        target = np.flipud(target).copy()
    if rng.random() < 0.6:
        angle = float(rng.uniform(-15.0, 15.0))
        height, width = target.shape
        matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
        image = cv2.warpAffine(
            image,
            matrix,
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )
        target = cv2.warpAffine(
            target,
            matrix,
            (width, height),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
    if rng.random() < 0.7:
        alpha = float(rng.uniform(0.90, 1.10))
        beta = float(rng.uniform(-8.0, 8.0))
        image = np.clip(image.astype(np.float32) * alpha + beta, 0, 255).astype(
            np.uint8
        )
    if rng.random() < 0.4:
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV).astype(np.float32)
        hsv[:, :, 1] *= float(rng.uniform(0.94, 1.06))
        image = cv2.cvtColor(
            np.clip(hsv, 0, 255).astype(np.uint8),
            cv2.COLOR_HSV2RGB,
        )
    return image, target


def _load_image_rgb(path: Path) -> np.ndarray:
    try:
        with Image.open(path) as source:
            return np.asarray(ImageOps.exif_transpose(source).convert("RGB"))
    except (OSError, UnidentifiedImageError) as exc:
        raise MulticlassBaselineError("image could not be decoded") from exc


class MulticlassWoundDataset(Dataset):
    def __init__(
        self,
        samples: Sequence[AuditSample],
        taxonomy: TissueTaxonomy,
        *,
        image_size: int,
        training: bool,
        seed: int = 42,
        allow_vertical_flip: bool = False,
    ):
        self.samples = list(samples)
        self.taxonomy = taxonomy
        self.image_size = image_size
        self.training = training
        self.seed = seed
        self.allow_vertical_flip = allow_vertical_flip
        self.epoch = 0

    def __len__(self) -> int:
        return len(self.samples)

    def set_epoch(self, epoch: int) -> None:
        self.epoch = epoch

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        sample = self.samples[index]
        if sample.mask_path is None:
            raise MulticlassBaselineError(f"{sample.sample_id}: missing mask")
        image = _load_image_rgb(sample.image_path)
        try:
            mask = read_indexed_mask(sample.mask_path)
        except MaskReviewError as exc:
            raise MulticlassBaselineError(
                f"{sample.sample_id}: invalid mask"
            ) from exc
        if image.shape[:2] != mask.shape:
            raise MulticlassBaselineError(
                f"{sample.sample_id}: image and mask size mismatch"
            )
        unexpected = set(np.unique(mask).tolist()) - set(
            self.taxonomy.allowed_mask_values
        )
        if unexpected:
            raise MulticlassBaselineError(
                f"{sample.sample_id}: values outside taxonomy"
            )

        if self.training:
            rng = np.random.default_rng(
                self.seed + (self.epoch * max(len(self.samples), 1)) + index
            )
            image, mask = augment_image_and_mask(
                image,
                mask,
                rng=rng,
                allow_vertical_flip=self.allow_vertical_flip,
            )
        image, mask = letterbox_image_and_mask(
            image,
            mask,
            size=self.image_size,
        )
        image_tensor = torch.from_numpy(
            np.ascontiguousarray(image.transpose(2, 0, 1))
        ).float() / 255.0
        mask_tensor = torch.from_numpy(np.ascontiguousarray(mask)).long()
        return image_tensor, mask_tensor


def _normalization_groups(channels: int) -> int:
    for groups in (8, 4, 2):
        if channels % groups == 0:
            return groups
    return 1


class _DoubleConv(nn.Module):
    def __init__(self, input_channels: int, output_channels: int):
        super().__init__()
        groups = _normalization_groups(output_channels)
        self.layers = nn.Sequential(
            nn.Conv2d(input_channels, output_channels, kernel_size=3, padding=1, bias=False),
            nn.GroupNorm(groups, output_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(output_channels, output_channels, kernel_size=3, padding=1, bias=False),
            nn.GroupNorm(groups, output_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.layers(inputs)


class _UpBlock(nn.Module):
    def __init__(self, input_channels: int, skip_channels: int, output_channels: int):
        super().__init__()
        self.reduce = nn.Conv2d(input_channels, output_channels, kernel_size=1)
        self.conv = _DoubleConv(output_channels + skip_channels, output_channels)

    def forward(self, inputs: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        inputs = F.interpolate(
            inputs,
            size=skip.shape[-2:],
            mode="bilinear",
            align_corners=False,
        )
        return self.conv(torch.cat([self.reduce(inputs), skip], dim=1))


class MulticlassUNet(nn.Module):
    """Compact GroupNorm U-Net suitable for small-batch baseline experiments."""

    def __init__(
        self,
        *,
        num_classes: int,
        input_channels: int = 3,
        base_channels: int = 16,
    ):
        super().__init__()
        if num_classes < 2:
            raise MulticlassBaselineError("num_classes must be at least two")
        channels = [
            base_channels,
            base_channels * 2,
            base_channels * 4,
            base_channels * 8,
        ]
        self.encoder_1 = _DoubleConv(input_channels, channels[0])
        self.encoder_2 = _DoubleConv(channels[0], channels[1])
        self.encoder_3 = _DoubleConv(channels[1], channels[2])
        self.encoder_4 = _DoubleConv(channels[2], channels[3])
        self.bottleneck = _DoubleConv(channels[3], channels[3] * 2)
        self.pool = nn.MaxPool2d(2)
        self.up_4 = _UpBlock(channels[3] * 2, channels[3], channels[3])
        self.up_3 = _UpBlock(channels[3], channels[2], channels[2])
        self.up_2 = _UpBlock(channels[2], channels[1], channels[1])
        self.up_1 = _UpBlock(channels[1], channels[0], channels[0])
        self.output = nn.Conv2d(channels[0], num_classes, kernel_size=1)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        skip_1 = self.encoder_1(inputs)
        skip_2 = self.encoder_2(self.pool(skip_1))
        skip_3 = self.encoder_3(self.pool(skip_2))
        skip_4 = self.encoder_4(self.pool(skip_3))
        features = self.bottleneck(self.pool(skip_4))
        features = self.up_4(features, skip_4)
        features = self.up_3(features, skip_3)
        features = self.up_2(features, skip_2)
        features = self.up_1(features, skip_1)
        return self.output(features)


class MulticlassSegmentationLoss(nn.Module):
    def __init__(
        self,
        *,
        num_classes: int,
        ignore_index: int = 255,
        loss_name: str = "cross_entropy_dice",
        class_weights: torch.Tensor | None = None,
        dice_weight: float = 0.5,
    ):
        super().__init__()
        self.num_classes = num_classes
        self.ignore_index = ignore_index
        self.loss_name = loss_name
        self.dice_weight = dice_weight
        if class_weights is None:
            self.register_buffer("class_weights", torch.ones(num_classes))
        else:
            self.register_buffer("class_weights", class_weights.float())

    def _valid_targets(
        self,
        logits: torch.Tensor,
        targets: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        valid = targets != self.ignore_index
        safe_targets = targets.masked_fill(~valid, 0)
        probs = torch.softmax(logits, dim=1)
        one_hot = (
            F.one_hot(safe_targets, num_classes=self.num_classes)
            .permute(0, 3, 1, 2)
            .float()
        )
        valid_channel = valid.unsqueeze(1)
        return safe_targets, probs * valid_channel, one_hot * valid_channel, valid

    def _dice_loss(
        self,
        probs: torch.Tensor,
        one_hot: torch.Tensor,
    ) -> torch.Tensor:
        intersection = (probs * one_hot).sum(dim=(0, 2, 3))
        denominator = probs.sum(dim=(0, 2, 3)) + one_hot.sum(dim=(0, 2, 3))
        dice = (2.0 * intersection + 1.0) / (denominator + 1.0)
        weights = self.class_weights / self.class_weights.sum()
        return 1.0 - (dice * weights).sum()

    def _focal_loss(
        self,
        logits: torch.Tensor,
        safe_targets: torch.Tensor,
        valid: torch.Tensor,
        gamma: float = 2.0,
    ) -> torch.Tensor:
        log_probs = F.log_softmax(logits, dim=1)
        selected = log_probs.gather(1, safe_targets.unsqueeze(1)).squeeze(1)
        selected_probs = selected.exp()
        weights = self.class_weights[safe_targets]
        focal = -weights * torch.pow(1.0 - selected_probs, gamma) * selected
        return focal[valid].mean()

    def _focal_tversky(
        self,
        probs: torch.Tensor,
        one_hot: torch.Tensor,
        gamma: float = 1.33,
    ) -> torch.Tensor:
        true_positive = (probs * one_hot).sum(dim=(0, 2, 3))
        false_positive = (probs * (1.0 - one_hot)).sum(dim=(0, 2, 3))
        false_negative = ((1.0 - probs) * one_hot).sum(dim=(0, 2, 3))
        tversky = (true_positive + 1.0) / (
            true_positive
            + (0.3 * false_positive)
            + (0.7 * false_negative)
            + 1.0
        )
        weights = self.class_weights / self.class_weights.sum()
        return (torch.pow(1.0 - tversky, gamma) * weights).sum()

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        safe_targets, probs, one_hot, valid = self._valid_targets(logits, targets)
        if not torch.any(valid):
            return logits.sum() * 0.0
        dice = self._dice_loss(probs, one_hot)
        if self.loss_name == "focal_tversky":
            return self._focal_tversky(probs, one_hot)
        if self.loss_name == "focal_dice":
            primary = self._focal_loss(logits, safe_targets, valid)
        elif self.loss_name == "cross_entropy_dice":
            primary = F.cross_entropy(
                logits,
                targets,
                weight=self.class_weights,
                ignore_index=self.ignore_index,
            )
        else:
            raise MulticlassBaselineError("unsupported loss_name")
        return ((1.0 - self.dice_weight) * primary) + (self.dice_weight * dice)


def calculate_training_class_weights(
    samples: Sequence[AuditSample],
    taxonomy: TissueTaxonomy,
    *,
    max_weight: float = 10.0,
) -> torch.Tensor:
    counts = np.zeros(taxonomy.num_classes, dtype=np.int64)
    for sample in samples:
        if sample.mask_path is None:
            raise MulticlassBaselineError(f"{sample.sample_id}: missing mask")
        try:
            mask = read_indexed_mask(sample.mask_path)
        except MaskReviewError as exc:
            raise MulticlassBaselineError(
                f"{sample.sample_id}: invalid mask"
            ) from exc
        for value in taxonomy.trainable_values:
            counts[value] += int((mask == value).sum())
    if np.any(counts == 0):
        raise MulticlassBaselineError(
            "every trainable class must occur in the training fold"
        )
    inverse_frequency = counts.sum() / (taxonomy.num_classes * counts)
    normalized = inverse_frequency / inverse_frequency.mean()
    return torch.tensor(
        np.clip(normalized, 0.1, max_weight),
        dtype=torch.float32,
    )


def _epoch_metrics(
    confusion: np.ndarray,
    *,
    background_index: int = 0,
) -> dict[str, Any]:
    dice = per_class_dice(confusion)
    iou = per_class_iou(confusion)
    precision = per_class_precision(confusion)
    recall = per_class_recall(confusion)
    specificity = per_class_specificity(confusion)
    foreground = [
        index for index in range(confusion.shape[0]) if index != background_index
    ]
    return {
        "confusion_matrix": confusion.tolist(),
        "dice_per_class": dice,
        "iou_per_class": iou,
        "precision_per_class": precision,
        "recall_per_class": recall,
        "specificity_per_class": specificity,
        "f1_per_class": dice,
        "weighted_dice": weighted_dice(confusion),
        "macro_dice_with_background": float(np.mean(dice)),
        "macro_iou_with_background": float(np.mean(iou)),
        "macro_dice_without_background": float(
            np.mean([dice[index] for index in foreground])
        ),
        "macro_iou_without_background": float(
            np.mean([iou[index] for index in foreground])
        ),
    }


def train_multiclass_baseline(
    train_samples: Sequence[AuditSample],
    validation_samples: Sequence[AuditSample],
    taxonomy: TissueTaxonomy,
    config: MulticlassBaselineConfig,
    *,
    output_dir: str | Path,
    device_name: str = "auto",
    resume: bool = False,
) -> dict[str, Any]:
    config.validate()
    if not taxonomy.clinically_validated:
        raise MulticlassBaselineError(
            "training requires a clinically validated taxonomy"
        )
    if not train_samples or not validation_samples:
        raise MulticlassBaselineError("training and validation samples are required")
    if device_name not in {"auto", "cpu", "cuda"}:
        raise MulticlassBaselineError("device_name must be auto, cpu, or cuda")
    if device_name == "cuda" and not torch.cuda.is_available():
        raise MulticlassBaselineError("CUDA was requested but is unavailable")

    set_reproducible_seed(config.seed, deterministic=config.deterministic)
    device = torch.device(
        "cuda"
        if device_name == "cuda"
        or (device_name == "auto" and torch.cuda.is_available())
        else "cpu"
    )
    train_dataset = MulticlassWoundDataset(
        train_samples,
        taxonomy,
        image_size=config.image_size,
        training=True,
        seed=config.seed,
        allow_vertical_flip=config.allow_vertical_flip,
    )
    validation_dataset = MulticlassWoundDataset(
        validation_samples,
        taxonomy,
        image_size=config.image_size,
        training=False,
        seed=config.seed,
    )
    generator = torch.Generator().manual_seed(config.seed)
    train_loader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        shuffle=True,
        generator=generator,
        num_workers=config.num_workers,
    )
    validation_loader = DataLoader(
        validation_dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
    )

    model = MulticlassUNet(
        num_classes=taxonomy.num_classes,
        base_channels=config.base_channels,
    ).to(device)
    class_weights = calculate_training_class_weights(
        train_samples,
        taxonomy,
    ).to(device)
    criterion = MulticlassSegmentationLoss(
        num_classes=taxonomy.num_classes,
        ignore_index=taxonomy.ignore_index,
        loss_name=config.loss_name,
        class_weights=class_weights,
        dice_weight=config.dice_weight,
    )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=max(config.epochs, 1),
    )
    use_amp = config.mixed_precision and device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    best_path = destination / "best_multiclass_unet.pt"
    last_path = destination / "last_multiclass_unet.pt"
    history: list[dict[str, Any]] = []
    best_score = -1.0
    start_epoch = 0
    patience = 0

    if resume:
        if not last_path.is_file():
            raise MulticlassBaselineError("resume requested but last checkpoint is missing")
        checkpoint = torch.load(last_path, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint["model_state_dict"])
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        scheduler.load_state_dict(checkpoint["scheduler_state_dict"])
        history = list(checkpoint.get("history", []))
        best_score = float(checkpoint.get("best_score", -1.0))
        start_epoch = int(checkpoint["epoch"]) + 1

    def run_validation() -> tuple[float, dict[str, Any]]:
        model.eval()
        losses: list[float] = []
        confusion = np.zeros(
            (taxonomy.num_classes, taxonomy.num_classes),
            dtype=np.int64,
        )
        with torch.no_grad():
            for images, masks in validation_loader:
                images = images.to(device)
                masks = masks.to(device)
                logits = model(images)
                loss = criterion(logits, masks)
                losses.append(float(loss.item()))
                predictions = logits.argmax(dim=1).cpu().numpy()
                confusion += multiclass_confusion_matrix(
                    predictions,
                    masks.cpu().numpy(),
                    num_classes=taxonomy.num_classes,
                )
        metrics = _epoch_metrics(confusion)
        return float(np.mean(losses)) if losses else 0.0, metrics

    for epoch in range(start_epoch, config.epochs):
        train_dataset.set_epoch(epoch)
        model.train()
        optimizer.zero_grad(set_to_none=True)
        train_losses: list[float] = []
        for step, (images, masks) in enumerate(train_loader):
            images = images.to(device)
            masks = masks.to(device)
            with torch.amp.autocast(device_type=device.type, enabled=use_amp):
                logits = model(images)
                loss = criterion(logits, masks)
                scaled_loss = loss / config.gradient_accumulation_steps
            scaler.scale(scaled_loss).backward()
            should_step = (
                (step + 1) % config.gradient_accumulation_steps == 0
                or step + 1 == len(train_loader)
            )
            if should_step:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(
                    model.parameters(),
                    config.gradient_clip_norm,
                )
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
            train_losses.append(float(loss.item()))

        validation_loss, validation_metrics = run_validation()
        scheduler.step()
        epoch_result = {
            "epoch": epoch,
            "train_loss": float(np.mean(train_losses)) if train_losses else 0.0,
            "validation_loss": validation_loss,
            "learning_rate": float(optimizer.param_groups[0]["lr"]),
            **validation_metrics,
        }
        history.append(epoch_result)
        score = validation_metrics["macro_dice_without_background"]
        checkpoint = {
            "schema_version": "1.0",
            "model_architecture": "compact_groupnorm_unet",
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "scheduler_state_dict": scheduler.state_dict(),
            "epoch": epoch,
            "best_score": max(best_score, score),
            "history": history,
            "config": asdict(config),
            "taxonomy_version": taxonomy.taxonomy_version,
            "class_names": {
                str(item.value): item.key
                for item in taxonomy.trainable_classes
            },
            "class_weights": class_weights.detach().cpu().tolist(),
            "research_only": True,
        }
        torch.save(checkpoint, last_path)
        if score > best_score:
            best_score = score
            patience = 0
            torch.save(checkpoint, best_path)
        else:
            patience += 1
            if (
                config.early_stopping_patience > 0
                and patience >= config.early_stopping_patience
            ):
                break

    metadata = {
        "schema_version": "1.0",
        "status": "research_only_not_clinically_validated",
        "model_architecture": "compact_groupnorm_unet",
        "taxonomy_version": taxonomy.taxonomy_version,
        "best_validation_macro_dice_without_background": best_score,
        "epochs_completed": len(history),
        "history": history,
        "device": device.type,
        "mixed_precision_used": use_amp,
        "test_set_used": False,
        "warnings": [
            "Model output requires professional review.",
            "Validation performance is not evidence of clinical readiness.",
        ],
    }
    (destination / "training_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metadata
