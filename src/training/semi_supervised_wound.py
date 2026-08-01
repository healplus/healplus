"""Binary teacher-student wound segmentation with controlled pseudo-labels."""

from __future__ import annotations

import csv
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torch.utils.data import DataLoader, Dataset

from src.processing.wound_segmentation_dl import (
    MODEL_ARCHITECTURE,
    SmallUNet,
    clean_binary_mask,
    letterbox_pil,
    undo_letterbox,
)

from .guided_wound_annotation import AnnotationItem, AnnotationWorkspace
from .multiclass_baseline import augment_image_and_mask

IGNORE_INDEX = 255


class SemiSupervisedWoundError(ValueError):
    """Raised when the teacher-student workflow cannot run safely."""


@dataclass(frozen=True, slots=True)
class BinaryTrainingSample:
    sample_id: str
    image_path: Path
    mask_path: Path
    source_type: str
    training_weight: float


@dataclass(frozen=True, slots=True)
class SemiSupervisedWoundConfig:
    minimum_human_masks: int = 100
    image_size: int = 256
    base_channels: int = 16
    batch_size: int = 4
    teacher_epochs: int = 15
    student_epochs: int = 15
    learning_rate: float = 3e-4
    weight_decay: float = 1e-4
    pseudo_label_weight: float = 0.30
    foreground_threshold: float = 0.90
    background_threshold: float = 0.10
    minimum_confident_pixel_ratio: float = 0.70
    minimum_foreground_ratio: float = 0.0005
    maximum_foreground_ratio: float = 0.95
    gradient_clip_norm: float = 1.0
    num_workers: int = 0
    seed: int = 42
    mixed_precision: bool = True

    def validate(self) -> None:
        if self.minimum_human_masks < 1:
            raise SemiSupervisedWoundError("minimum_human_masks must be positive")
        if self.image_size < 32 or self.image_size % 8:
            raise SemiSupervisedWoundError("image_size must be >= 32 and divisible by eight")
        if self.batch_size <= 0 or self.teacher_epochs <= 0 or self.student_epochs <= 0:
            raise SemiSupervisedWoundError("batch size and epoch counts must be positive")
        if not 0.0 < self.background_threshold < 0.5:
            raise SemiSupervisedWoundError("background_threshold must be between zero and 0.5")
        if not 0.5 < self.foreground_threshold < 1.0:
            raise SemiSupervisedWoundError("foreground_threshold must be between 0.5 and one")
        if not 0.0 < self.pseudo_label_weight < 1.0:
            raise SemiSupervisedWoundError("pseudo_label_weight must be between zero and one")
        if not 0.0 <= self.minimum_confident_pixel_ratio <= 1.0:
            raise SemiSupervisedWoundError("minimum_confident_pixel_ratio must be between zero and one")
        if not (0.0 <= self.minimum_foreground_ratio < self.maximum_foreground_ratio <= 1.0):
            raise SemiSupervisedWoundError("foreground ratio limits must satisfy 0 <= minimum < maximum <= 1")


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True


def _resolve_device(device_name: str) -> torch.device:
    if device_name not in {"auto", "cpu", "cuda"}:
        raise SemiSupervisedWoundError("device must be auto, cpu, or cuda")
    if device_name == "cuda" and not torch.cuda.is_available():
        raise SemiSupervisedWoundError("CUDA was requested but is unavailable")
    if device_name == "cuda" or (device_name == "auto" and torch.cuda.is_available()):
        return torch.device("cuda")
    return torch.device("cpu")


def human_training_samples(
    workspace: AnnotationWorkspace,
) -> list[BinaryTrainingSample]:
    return [
        BinaryTrainingSample(
            sample_id=item.sample_id,
            image_path=workspace.ensure_normalized_image(item),
            mask_path=item.human_mask_path,
            source_type="human",
            training_weight=1.0,
        )
        for item in workspace.approved_items()
    ]


def pseudo_training_samples(
    workspace: AnnotationWorkspace,
    *,
    pseudo_label_weight: float,
) -> list[BinaryTrainingSample]:
    approved = {item.sample_id for item in workspace.approved_items()}
    samples: list[BinaryTrainingSample] = []
    for item in workspace.items:
        record = workspace.record(item.sample_id)
        if (
            item.sample_id not in approved
            and record.get("status") == "pseudo_pending_review"
            and record.get("pseudo_training_eligible") is True
            and item.pseudo_mask_path.is_file()
        ):
            samples.append(
                BinaryTrainingSample(
                    sample_id=item.sample_id,
                    image_path=workspace.ensure_normalized_image(item),
                    mask_path=item.pseudo_mask_path,
                    source_type="pseudo",
                    training_weight=pseudo_label_weight,
                )
            )
    return samples


class _BinaryWoundDataset(Dataset):
    def __init__(
        self,
        samples: Sequence[BinaryTrainingSample],
        *,
        image_size: int,
        seed: int,
        augment: bool,
    ):
        self.samples = list(samples)
        self.image_size = image_size
        self.seed = seed
        self.augment = augment
        self.epoch = 0

    def set_epoch(self, epoch: int) -> None:
        self.epoch = epoch

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(
        self,
        index: int,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        sample = self.samples[index]
        with Image.open(sample.image_path) as source:
            image = np.asarray(source.convert("RGB"))
        raw_mask = cv2.imread(str(sample.mask_path), cv2.IMREAD_GRAYSCALE)
        if raw_mask is None or raw_mask.shape != image.shape[:2]:
            raise SemiSupervisedWoundError(f"{sample.sample_id}: image/mask pair is invalid")
        if sample.source_type == "pseudo":
            unexpected = set(np.unique(raw_mask).tolist()) - {0, 1, IGNORE_INDEX}
            if unexpected:
                raise SemiSupervisedWoundError(f"{sample.sample_id}: pseudo-mask values are invalid")
            mask = raw_mask
        else:
            mask = (raw_mask > 0).astype(np.uint8)

        if self.augment:
            rng = np.random.default_rng(self.seed + (self.epoch * max(len(self.samples), 1)) + index)
            image, mask = augment_image_and_mask(image, mask, rng=rng)
        image_pil, _ = letterbox_pil(
            Image.fromarray(image, mode="RGB"),
            self.image_size,
            resample=Image.Resampling.BILINEAR,
            fill=(0, 0, 0),
        )
        mask_pil, _ = letterbox_pil(
            Image.fromarray(mask, mode="L"),
            self.image_size,
            resample=Image.Resampling.NEAREST,
            fill=0,
        )
        image_array = np.array(image_pil, dtype=np.float32, copy=True) / 255.0
        mask_array = np.array(mask_pil, dtype=np.uint8, copy=True)
        return (
            torch.from_numpy(np.ascontiguousarray(image_array.transpose(2, 0, 1))),
            torch.from_numpy(np.ascontiguousarray(mask_array)).long(),
            torch.tensor(sample.training_weight, dtype=torch.float32),
        )


def semi_supervised_binary_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    sample_weights: torch.Tensor,
    *,
    positive_weight: torch.Tensor | None = None,
) -> torch.Tensor:
    if logits.ndim != 4 or logits.shape[1] != 1:
        raise SemiSupervisedWoundError("binary logits must have shape B x 1 x H x W")
    logits_2d = logits[:, 0]
    valid = targets != IGNORE_INDEX
    safe_targets = targets.masked_fill(~valid, 0).float()
    pixel_loss = F.binary_cross_entropy_with_logits(
        logits_2d,
        safe_targets,
        reduction="none",
        pos_weight=positive_weight,
    )
    valid_float = valid.float()
    bce_per_sample = (pixel_loss * valid_float).sum(dim=(1, 2)) / valid_float.sum(dim=(1, 2)).clamp_min(1.0)
    probabilities = torch.sigmoid(logits_2d) * valid_float
    target_valid = safe_targets * valid_float
    intersection = (probabilities * target_valid).sum(dim=(1, 2))
    denominator = probabilities.sum(dim=(1, 2)) + target_valid.sum(dim=(1, 2))
    dice_loss = 1.0 - ((2.0 * intersection + 1.0) / (denominator + 1.0))
    valid_samples = valid.flatten(1).any(dim=1)
    combined = 0.5 * bce_per_sample + 0.5 * dice_loss
    effective_weights = sample_weights * valid_samples.float()
    return (combined * effective_weights).sum() / effective_weights.sum().clamp_min(1e-6)


def _positive_weight_from_humans(
    samples: Sequence[BinaryTrainingSample],
) -> torch.Tensor:
    positive = 0
    negative = 0
    for sample in samples:
        if sample.source_type != "human":
            continue
        mask = cv2.imread(str(sample.mask_path), cv2.IMREAD_GRAYSCALE)
        if mask is None:
            raise SemiSupervisedWoundError(f"{sample.sample_id}: human mask could not be decoded")
        positive += int((mask > 0).sum())
        negative += int((mask == 0).sum())
    if positive == 0:
        raise SemiSupervisedWoundError("human masks contain no wound pixels")
    return torch.tensor(
        min(max(negative / positive, 0.25), 20.0),
        dtype=torch.float32,
    )


def train_binary_stage(
    samples: Sequence[BinaryTrainingSample],
    config: SemiSupervisedWoundConfig,
    *,
    output_path: str | Path,
    stage: str,
    epochs: int,
    device_name: str = "auto",
    initial_checkpoint: str | Path | None = None,
) -> dict[str, Any]:
    config.validate()
    if not samples:
        raise SemiSupervisedWoundError("training stage has no samples")
    if stage not in {"teacher", "student"}:
        raise SemiSupervisedWoundError("stage must be teacher or student")
    human_count = sum(sample.source_type == "human" for sample in samples)
    if human_count < config.minimum_human_masks:
        raise SemiSupervisedWoundError(f"at least {config.minimum_human_masks} human masks are required")
    if stage == "teacher" and any(sample.source_type != "human" for sample in samples):
        raise SemiSupervisedWoundError("teacher stage must use human masks only")
    _set_seed(config.seed)
    device = _resolve_device(device_name)
    dataset = _BinaryWoundDataset(
        samples,
        image_size=config.image_size,
        seed=config.seed,
        augment=True,
    )
    loader = DataLoader(
        dataset,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=config.num_workers,
        generator=torch.Generator().manual_seed(config.seed),
    )
    model = SmallUNet(base_channels=config.base_channels).to(device)
    if initial_checkpoint:
        checkpoint = torch.load(
            initial_checkpoint,
            map_location=device,
            weights_only=False,
        )
        model.load_state_dict(checkpoint["model_state_dict"])
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=max(epochs, 1),
    )
    positive_weight = _positive_weight_from_humans(samples).to(device)
    use_amp = config.mixed_precision and device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    history: list[dict[str, float | int]] = []
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    for epoch in range(epochs):
        dataset.set_epoch(epoch)
        model.train()
        losses: list[float] = []
        for images, masks, sample_weights in loader:
            images = images.to(device)
            masks = masks.to(device)
            sample_weights = sample_weights.to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast(device_type=device.type, enabled=use_amp):
                logits = model(images)
                loss = semi_supervised_binary_loss(
                    logits,
                    masks,
                    sample_weights,
                    positive_weight=positive_weight,
                )
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                config.gradient_clip_norm,
            )
            scaler.step(optimizer)
            scaler.update()
            losses.append(float(loss.item()))
        scheduler.step()
        history.append(
            {
                "epoch": epoch,
                "training_loss": float(np.mean(losses)) if losses else 0.0,
                "learning_rate": float(optimizer.param_groups[0]["lr"]),
            }
        )
        checkpoint = {
            "schema_version": "1.0",
            "architecture": MODEL_ARCHITECTURE,
            "base_channels": config.base_channels,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "epoch": epoch,
            "stage": stage,
            "model_version": f"binary-{stage}-epoch-{epoch + 1}",
            "training_args": {
                "image_size": config.image_size,
                "seed": config.seed,
            },
            "human_samples": sum(sample.source_type == "human" for sample in samples),
            "pseudo_samples": sum(sample.source_type == "pseudo" for sample in samples),
            "pseudo_label_weight": config.pseudo_label_weight,
            "history": history,
            "validation_used": False,
            "test_set_used": False,
            "clinical_status": "experimental_requires_professional_review",
            "license_scope": "private_internal_research_only",
        }
        torch.save(checkpoint, output)

    return {
        "checkpoint": str(output),
        "stage": stage,
        "epochs": epochs,
        "human_samples": checkpoint["human_samples"],
        "pseudo_samples": checkpoint["pseudo_samples"],
        "device": device.type,
        "mixed_precision_used": use_amp,
        "validation_used": False,
        "test_set_used": False,
        "history": history,
    }


def generate_pseudo_labels(
    workspace: AnnotationWorkspace,
    teacher_checkpoint: str | Path,
    config: SemiSupervisedWoundConfig,
    *,
    device_name: str = "auto",
) -> dict[str, Any]:
    config.validate()
    device = _resolve_device(device_name)
    checkpoint = torch.load(
        teacher_checkpoint,
        map_location=device,
        weights_only=False,
    )
    model = SmallUNet(base_channels=int(checkpoint["base_channels"])).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    teacher_version = str(checkpoint["model_version"])
    rows: list[dict[str, Any]] = []

    for item in workspace.unapproved_items():
        normalized_path = workspace.ensure_normalized_image(item)
        with Image.open(normalized_path) as source:
            image = source.convert("RGB")
            prepared, metadata = letterbox_pil(
                image,
                config.image_size,
                resample=Image.Resampling.BILINEAR,
                fill=(0, 0, 0),
            )
        image_array = np.array(prepared, dtype=np.float32, copy=True) / 255.0
        tensor = torch.from_numpy(np.ascontiguousarray(image_array.transpose(2, 0, 1))).unsqueeze(0).to(device)
        with torch.inference_mode():
            logits = model(tensor)
            prepared_probabilities = torch.sigmoid(logits)[0, 0].cpu().numpy()
        probabilities = undo_letterbox(
            prepared_probabilities,
            metadata,
            interpolation=cv2.INTER_LINEAR,
        )
        confidence_map = np.maximum(probabilities, 1.0 - probabilities)
        pseudo_mask = np.full(probabilities.shape, IGNORE_INDEX, dtype=np.uint8)
        pseudo_mask[probabilities <= config.background_threshold] = 0
        pseudo_mask[probabilities >= config.foreground_threshold] = 1
        confident = pseudo_mask != IGNORE_INDEX
        confident_ratio = float(confident.mean())
        foreground_ratio = float((pseudo_mask == 1).sum() / max(int(confident.sum()), 1))
        confidence = float(confidence_map.mean())
        accepted = (
            confident_ratio >= config.minimum_confident_pixel_ratio
            and config.minimum_foreground_ratio <= foreground_ratio <= config.maximum_foreground_ratio
        )
        if accepted:
            if not cv2.imwrite(str(item.pseudo_mask_path), pseudo_mask):
                raise SemiSupervisedWoundError("pseudo-mask could not be saved")
        elif item.pseudo_mask_path.exists():
            item.pseudo_mask_path.unlink()
        workspace.register_pseudo_mask(
            item,
            confidence=confidence,
            confident_pixel_ratio=confident_ratio,
            foreground_ratio=foreground_ratio,
            teacher_version=teacher_version,
            accepted=accepted,
        )
        rows.append(
            {
                "sample_id": item.sample_id,
                "status": "pending_review" if accepted else "rejected",
                "confidence": round(confidence, 6),
                "confident_pixel_ratio": round(confident_ratio, 6),
                "foreground_ratio": round(foreground_ratio, 6),
            }
        )

    review_csv = workspace.workspace_root / "pseudo_label_review_queue.csv"
    with review_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "sample_id",
                "status",
                "confidence",
                "confident_pixel_ratio",
                "foreground_ratio",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "teacher_version": teacher_version,
        "unlabeled_images_processed": len(rows),
        "accepted_pseudo_labels": sum(row["status"] == "pending_review" for row in rows),
        "rejected_pseudo_labels": sum(row["status"] == "rejected" for row in rows),
        "review_queue": str(review_csv),
        "thresholds": {
            "background": config.background_threshold,
            "foreground": config.foreground_threshold,
            "minimum_confident_pixel_ratio": config.minimum_confident_pixel_ratio,
        },
    }
    (workspace.workspace_root / "pseudo_label_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def generate_human_review_suggestions(
    workspace: AnnotationWorkspace,
    teacher_checkpoint: str | Path,
    config: SemiSupervisedWoundConfig,
    *,
    count: int = 20,
    device_name: str = "auto",
) -> dict[str, Any]:
    """Create review-only 0.5 masks when confidence gates accept no pseudo-labels."""

    if count <= 0:
        raise SemiSupervisedWoundError("review suggestion count must be positive")
    device = _resolve_device(device_name)
    checkpoint = torch.load(
        teacher_checkpoint,
        map_location=device,
        weights_only=False,
    )
    model = SmallUNet(base_channels=int(checkpoint["base_channels"])).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    teacher_version = str(checkpoint["model_version"])
    candidates: list[tuple[float, AnnotationItem, np.ndarray, float]] = []

    for item in workspace.unapproved_items():
        normalized_path = workspace.ensure_normalized_image(item)
        with Image.open(normalized_path) as source:
            image = source.convert("RGB")
            prepared, metadata = letterbox_pil(
                image,
                config.image_size,
                resample=Image.Resampling.BILINEAR,
                fill=(0, 0, 0),
            )
        image_array = np.array(prepared, dtype=np.float32, copy=True) / 255.0
        tensor = torch.from_numpy(np.ascontiguousarray(image_array.transpose(2, 0, 1))).unsqueeze(0).to(device)
        with torch.inference_mode():
            prepared_probabilities = torch.sigmoid(model(tensor))[0, 0].cpu().numpy()
        probabilities = undo_letterbox(
            prepared_probabilities,
            metadata,
            interpolation=cv2.INTER_LINEAR,
        )
        clipped = np.clip(probabilities, 1e-6, 1.0 - 1e-6)
        entropy = -(clipped * np.log2(clipped) + (1.0 - clipped) * np.log2(1.0 - clipped))
        uncertainty = float(entropy.mean())
        confidence = float(np.maximum(probabilities, 1.0 - probabilities).mean())
        binary = clean_binary_mask((probabilities >= 0.5).astype(np.uint8) * 255)
        candidates.append(
            (
                uncertainty,
                item,
                (binary > 0).astype(np.uint8),
                confidence,
            )
        )

    candidates.sort(key=lambda candidate: (-candidate[0], candidate[1].sample_id))
    selected = candidates[: min(count, len(candidates))]
    rows: list[dict[str, Any]] = []
    for uncertainty, item, mask, confidence in selected:
        if not cv2.imwrite(str(item.pseudo_mask_path), mask):
            raise SemiSupervisedWoundError("review suggestion could not be saved")
        foreground_ratio = float((mask == 1).mean())
        workspace.register_pseudo_mask(
            item,
            confidence=confidence,
            confident_pixel_ratio=1.0,
            foreground_ratio=foreground_ratio,
            teacher_version=teacher_version,
            accepted=True,
            training_eligible=False,
            suggestion_type="review_only_threshold_0_5",
        )
        rows.append(
            {
                "sample_id": item.sample_id,
                "mean_uncertainty": round(uncertainty, 6),
                "confidence": round(confidence, 6),
                "foreground_ratio": round(foreground_ratio, 6),
                "training_eligible": False,
            }
        )

    queue_path = workspace.workspace_root / "human_review_suggestions.csv"
    with queue_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "sample_id",
                "mean_uncertainty",
                "confidence",
                "foreground_ratio",
                "training_eligible",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return {
        "suggestions": len(rows),
        "teacher_version": teacher_version,
        "selection": "highest_mean_binary_entropy",
        "mask_threshold": 0.5,
        "training_eligible_before_human_review": False,
        "queue": str(queue_path),
    }


def write_augmentation_preview(
    workspace: AnnotationWorkspace,
    *,
    count: int = 20,
    seed: int = 42,
) -> Path:
    import matplotlib.pyplot as plt

    humans = human_training_samples(workspace)
    if not humans:
        raise SemiSupervisedWoundError("no human sample is available for preview")
    sample = humans[0]
    with Image.open(sample.image_path) as source:
        image = np.asarray(source.convert("RGB"))
    mask = cv2.imread(str(sample.mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise SemiSupervisedWoundError("preview mask could not be decoded")
    columns = 4
    rows = int(np.ceil(count / columns))
    figure, axes = plt.subplots(
        rows,
        columns,
        figsize=(columns * 3, rows * 3),
        squeeze=False,
    )
    for index, axis in enumerate(axes.ravel()):
        axis.axis("off")
        if index >= count:
            continue
        augmented_image, augmented_mask = augment_image_and_mask(
            image,
            (mask > 0).astype(np.uint8),
            rng=np.random.default_rng(seed + index),
        )
        overlay = augmented_image.astype(np.float32).copy()
        selected = augmented_mask > 0
        overlay[selected] = (0.55 * overlay[selected]) + (0.45 * np.array([239, 68, 68], dtype=np.float32))
        axis.imshow(np.clip(overlay, 0, 255).astype(np.uint8))
        axis.set_title(f"variação {index + 1}")
    figure.suptitle(f"{sample.sample_id} — augmentation sincronizada")
    figure.tight_layout()
    output = workspace.workspace_root / "augmentation_preview_20.png"
    figure.savefig(output, dpi=140)
    plt.close(figure)
    return output


def write_pipeline_report(
    workspace: AnnotationWorkspace,
    config: SemiSupervisedWoundConfig,
    *,
    teacher_result: dict[str, Any],
    pseudo_result: dict[str, Any],
    student_result: dict[str, Any] | None,
    augmentation_preview: Path,
) -> Path:
    student_pseudo_samples = int(student_result.get("pseudo_samples", 0)) if student_result is not None else 0
    if student_pseudo_samples > 0:
        status = "semi_supervised_student_trained"
    elif student_result is not None:
        status = "human_reviewed_student_trained_no_accepted_pseudo_labels"
    else:
        status = "teacher_trained_no_accepted_pseudo_labels"
    report = {
        "schema_version": "1.0",
        "status": status,
        "config": asdict(config),
        "approved_human_masks": workspace.approved_count,
        "teacher": teacher_result,
        "pseudo_labels": pseudo_result,
        "student": student_result,
        "augmentation_preview": str(augmentation_preview),
        "governance": {
            "original_images_modified": False,
            "pseudo_labels_are_ground_truth": False,
            "validation_used": False,
            "test_set_used": False,
            "clinical_use_allowed": False,
            "professional_review_required": True,
        },
    }
    path = workspace.workspace_root / "semi_supervised_pipeline_report.json"
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
