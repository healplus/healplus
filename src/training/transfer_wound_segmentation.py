"""Transfer-learning binary wound segmentation with LR-ASPP MobileNetV3."""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision.models import MobileNet_V3_Large_Weights
from torchvision.models.segmentation import (
    LRASPP_MobileNet_V3_Large_Weights,
    lraspp_mobilenet_v3_large,
)

from src.processing.wound_segmentation_dl import (
    clean_binary_mask,
    letterbox_pil,
    undo_letterbox,
)

from .binary_wound_validation import (
    BinaryWoundValidationError,
    _single_source_group,
    _summarize_rows,
)
from .guided_wound_annotation import AnnotationWorkspace
from .multiclass_baseline import augment_image_and_mask
from .segmentation_metrics import binary_dice_score, binary_iou_score
from .semi_supervised_wound import (
    IGNORE_INDEX,
    BinaryTrainingSample,
    SemiSupervisedWoundConfig,
    SemiSupervisedWoundError,
    semi_supervised_binary_loss,
)

LRASPP_ARCHITECTURE = "lraspp-mobilenet-v3-large-imagenet1k-binary-v1"
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class TransferWoundSegmentationError(ValueError):
    """Raised when transfer-learning training or evaluation cannot proceed."""


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True


def _device(device_name: str) -> torch.device:
    if device_name not in {"auto", "cpu", "cuda"}:
        raise TransferWoundSegmentationError("device must be auto, cpu, or cuda")
    if device_name == "cuda" and not torch.cuda.is_available():
        raise TransferWoundSegmentationError("CUDA was requested but is unavailable")
    return torch.device(
        "cuda" if device_name == "cuda" or (device_name == "auto" and torch.cuda.is_available()) else "cpu"
    )


def _collapse_classifier_to_objectness(
    classifier: torch.nn.Conv2d,
) -> torch.nn.Conv2d:
    binary = torch.nn.Conv2d(
        classifier.in_channels,
        1,
        kernel_size=classifier.kernel_size,
        stride=classifier.stride,
        padding=classifier.padding,
        dilation=classifier.dilation,
        bias=classifier.bias is not None,
    )
    with torch.no_grad():
        foreground_weight = classifier.weight[1:].mean(
            dim=0,
            keepdim=True,
        )
        binary.weight.copy_(foreground_weight - classifier.weight[:1])
        if classifier.bias is not None and binary.bias is not None:
            foreground_bias = classifier.bias[1:].mean().reshape(1)
            binary.bias.copy_(foreground_bias - classifier.bias[:1])
    return binary


def _new_model(*, pretraining: str) -> torch.nn.Module:
    if pretraining == "coco_segmentation":
        model = lraspp_mobilenet_v3_large(
            weights=LRASPP_MobileNet_V3_Large_Weights.DEFAULT,
        )
        model.classifier.low_classifier = _collapse_classifier_to_objectness(model.classifier.low_classifier)
        model.classifier.high_classifier = _collapse_classifier_to_objectness(model.classifier.high_classifier)
        return model
    if pretraining == "imagenet":
        return lraspp_mobilenet_v3_large(
            weights=None,
            weights_backbone=(MobileNet_V3_Large_Weights.IMAGENET1K_V1),
            num_classes=1,
        )
    if pretraining == "none":
        return lraspp_mobilenet_v3_large(
            weights=None,
            weights_backbone=None,
            num_classes=1,
        )
    raise TransferWoundSegmentationError("pretraining must be none, imagenet, or coco_segmentation")


class LRASPPBinaryDataset(Dataset):
    def __init__(
        self,
        samples: Sequence[BinaryTrainingSample],
        *,
        image_size: int,
        training: bool,
        seed: int,
    ):
        self.samples = list(samples)
        self.image_size = image_size
        self.training = training
        self.seed = seed
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
            raise TransferWoundSegmentationError(f"{sample.sample_id}: image/mask pair is invalid")
        if sample.source_type == "pseudo":
            unexpected = set(np.unique(raw_mask).tolist()) - {
                0,
                1,
                IGNORE_INDEX,
            }
            if unexpected:
                raise TransferWoundSegmentationError(f"{sample.sample_id}: pseudo-mask values are invalid")
            mask = raw_mask
        else:
            mask = (raw_mask > 0).astype(np.uint8)
        if self.training:
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
        image_array = (
            np.array(
                image_pil,
                dtype=np.float32,
                copy=True,
            )
            / 255.0
        )
        image_array = (image_array - IMAGENET_MEAN) / IMAGENET_STD
        mask_array = np.array(mask_pil, dtype=np.uint8, copy=True)
        return (
            torch.from_numpy(np.ascontiguousarray(image_array.transpose(2, 0, 1))),
            torch.from_numpy(np.ascontiguousarray(mask_array)).long(),
            torch.tensor(sample.training_weight, dtype=torch.float32),
        )


def _positive_weight(
    samples: Sequence[BinaryTrainingSample],
    *,
    strategy: str,
) -> torch.Tensor:
    positive = 0
    negative = 0
    for sample in samples:
        if sample.source_type != "human":
            continue
        mask = cv2.imread(str(sample.mask_path), cv2.IMREAD_GRAYSCALE)
        if mask is None:
            raise TransferWoundSegmentationError(f"{sample.sample_id}: human mask could not be decoded")
        positive += int((mask > 0).sum())
        negative += int((mask == 0).sum())
    if positive == 0:
        raise TransferWoundSegmentationError("human masks contain no wound pixels")
    ratio = negative / positive
    if strategy == "ratio":
        value = ratio
    elif strategy == "sqrt_ratio":
        value = float(np.sqrt(ratio))
    elif strategy == "none":
        value = 1.0
    else:
        raise TransferWoundSegmentationError("positive weight strategy must be ratio, sqrt_ratio, or none")
    return torch.tensor(
        min(max(value, 0.25), 20.0),
        dtype=torch.float32,
    )


def _validation_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    *,
    device: torch.device,
    positive_weight: torch.Tensor,
) -> dict[str, float]:
    model.eval()
    losses: list[float] = []
    dice_values: list[float] = []
    iou_values: list[float] = []
    with torch.inference_mode():
        for images, masks, sample_weights in loader:
            images = images.to(device)
            masks = masks.to(device)
            sample_weights = sample_weights.to(device)
            logits = model(images)["out"]
            loss = semi_supervised_binary_loss(
                logits,
                masks,
                sample_weights,
                positive_weight=positive_weight,
            )
            losses.append(float(loss.item()))
            predictions = torch.sigmoid(logits[:, 0]) >= 0.5
            for prediction, target in zip(predictions.cpu(), masks.cpu()):
                truth = target.numpy() > 0
                predicted = prediction.numpy()
                dice_values.append(binary_dice_score(predicted, truth, eps=0.0))
                iou_values.append(binary_iou_score(predicted, truth, eps=0.0))
    return {
        "validation_loss": float(np.mean(losses)),
        "validation_macro_dice": float(np.mean(dice_values)),
        "validation_macro_iou": float(np.mean(iou_values)),
    }


def train_lraspp_stage(
    train_samples: Sequence[BinaryTrainingSample],
    validation_samples: Sequence[BinaryTrainingSample],
    config: SemiSupervisedWoundConfig,
    *,
    output_path: str | Path,
    stage: str,
    epochs: int,
    device_name: str = "auto",
    initial_checkpoint: str | Path | None = None,
    patience: int = 8,
    minimum_epochs: int = 12,
    pretraining: str = "imagenet",
    positive_weight_strategy: str = "sqrt_ratio",
) -> dict[str, Any]:
    """Fine-tune ImageNet LR-ASPP and save the best validation checkpoint."""

    config.validate()
    if not train_samples or not validation_samples:
        raise TransferWoundSegmentationError("training and validation samples are required")
    if stage not in {"teacher", "student"}:
        raise TransferWoundSegmentationError("stage must be teacher or student")
    human_count = sum(sample.source_type == "human" for sample in train_samples)
    if human_count < config.minimum_human_masks:
        raise TransferWoundSegmentationError(f"at least {config.minimum_human_masks} human masks are required")
    if stage == "teacher" and any(sample.source_type != "human" for sample in train_samples):
        raise TransferWoundSegmentationError("teacher stage must use human masks only")
    _set_seed(config.seed)
    device = _device(device_name)
    model = _new_model(pretraining=(pretraining if initial_checkpoint is None else "none")).to(device)
    if initial_checkpoint:
        initial = torch.load(
            initial_checkpoint,
            map_location=device,
            weights_only=False,
        )
        if initial.get("architecture") != LRASPP_ARCHITECTURE:
            raise TransferWoundSegmentationError("initial checkpoint architecture is incompatible")
        model.load_state_dict(initial["model_state_dict"])

    train_dataset = LRASPPBinaryDataset(
        train_samples,
        image_size=config.image_size,
        training=True,
        seed=config.seed,
    )
    validation_dataset = LRASPPBinaryDataset(
        validation_samples,
        image_size=config.image_size,
        training=False,
        seed=config.seed,
    )
    train_loader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=config.num_workers,
        generator=torch.Generator().manual_seed(config.seed),
    )
    validation_loader = DataLoader(
        validation_dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
    )
    optimizer = torch.optim.AdamW(
        [
            {
                "params": model.backbone.parameters(),
                "lr": config.learning_rate * 0.25,
            },
            {
                "params": model.classifier.parameters(),
                "lr": config.learning_rate,
            },
        ],
        weight_decay=config.weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=max(epochs, 1),
    )
    positive_weight = _positive_weight(
        train_samples,
        strategy=positive_weight_strategy,
    ).to(device)
    use_amp = config.mixed_precision and device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    history: list[dict[str, Any]] = []
    best_score = -1.0
    best_epoch = -1
    epochs_without_improvement = 0
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    last_path = output.with_name(f"{output.stem}_last{output.suffix}")

    for epoch in range(epochs):
        train_dataset.set_epoch(epoch)
        model.train()
        losses: list[float] = []
        for images, masks, sample_weights in train_loader:
            images = images.to(device)
            masks = masks.to(device)
            sample_weights = sample_weights.to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast(
                device_type=device.type,
                enabled=use_amp,
            ):
                logits = model(images)["out"]
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
        validation = _validation_epoch(
            model,
            validation_loader,
            device=device,
            positive_weight=positive_weight,
        )
        scheduler.step()
        history.append(
            {
                "epoch": epoch + 1,
                "training_loss": float(np.mean(losses)),
                "learning_rate_backbone": float(optimizer.param_groups[0]["lr"]),
                "learning_rate_classifier": float(optimizer.param_groups[1]["lr"]),
                **validation,
            }
        )
        score = validation["validation_macro_dice"]
        improved = score > best_score + 1e-6
        if improved:
            best_score = score
            best_epoch = epoch + 1
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
        checkpoint = {
            "schema_version": "1.0",
            "architecture": LRASPP_ARCHITECTURE,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "epoch": epoch,
            "best_epoch": best_epoch,
            "best_validation_macro_dice": best_score,
            "stage": stage,
            "model_version": f"lraspp-{stage}-epoch-{epoch + 1}",
            "training_args": {
                "image_size": config.image_size,
                "seed": config.seed,
                "normalization": "imagenet",
            },
            "human_samples": human_count,
            "pseudo_samples": sum(sample.source_type == "pseudo" for sample in train_samples),
            "pseudo_label_weight": config.pseudo_label_weight,
            "decision_threshold": 0.5,
            "pretraining": (pretraining if initial_checkpoint is None else initial.get("pretraining", "checkpoint")),
            "positive_weight_strategy": positive_weight_strategy,
            "positive_weight": float(positive_weight.item()),
            "history": history,
            "validation_used": True,
            "test_set_used": False,
            "clinical_status": ("experimental_requires_external_clinical_validation"),
            "license_scope": "private_internal_research_only",
        }
        torch.save(checkpoint, last_path)
        if improved:
            torch.save(checkpoint, output)
        if epoch + 1 >= minimum_epochs and epochs_without_improvement >= patience:
            break

    best = torch.load(output, map_location="cpu", weights_only=False)
    return {
        "checkpoint": str(output),
        "last_checkpoint": str(last_path),
        "stage": stage,
        "epochs_completed": len(history),
        "best_epoch": int(best["best_epoch"]),
        "best_validation_macro_dice": float(best["best_validation_macro_dice"]),
        "human_samples": int(best["human_samples"]),
        "pseudo_samples": int(best["pseudo_samples"]),
        "device": device.type,
        "mixed_precision_used": use_amp,
        "pretraining": (pretraining if initial_checkpoint is None else "initial_checkpoint"),
        "positive_weight_strategy": positive_weight_strategy,
        "positive_weight": float(positive_weight.item()),
        "augmentation": {
            "horizontal_flip": True,
            "rotation_degrees": 15,
            "brightness_contrast": True,
            "saturation": True,
            "vertical_flip": False,
        },
        "validation_used": True,
        "test_set_used": False,
        "history": history,
    }


def _load_model(
    checkpoint_path: str | Path,
    device: torch.device,
) -> tuple[torch.nn.Module, dict[str, Any]]:
    checkpoint = torch.load(
        checkpoint_path,
        map_location=device,
        weights_only=False,
    )
    if checkpoint.get("architecture") != LRASPP_ARCHITECTURE:
        raise TransferWoundSegmentationError("checkpoint architecture is incompatible")
    model = _new_model(pretraining="none").to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model, checkpoint


def _predict_original(
    model: torch.nn.Module,
    image: Image.Image,
    *,
    image_size: int,
    device: torch.device,
) -> np.ndarray:
    prepared, metadata = letterbox_pil(
        image,
        image_size,
        resample=Image.Resampling.BILINEAR,
        fill=(0, 0, 0),
    )
    image_array = (
        np.array(
            prepared,
            dtype=np.float32,
            copy=True,
        )
        / 255.0
    )
    image_array = (image_array - IMAGENET_MEAN) / IMAGENET_STD
    tensor = torch.from_numpy(np.ascontiguousarray(image_array.transpose(2, 0, 1))).unsqueeze(0).to(device)
    with torch.inference_mode():
        prepared_probabilities = torch.sigmoid(model(tensor)["out"])[0, 0].cpu().numpy()
    return undo_letterbox(
        prepared_probabilities,
        metadata,
        interpolation=cv2.INTER_LINEAR,
    )


def calibrate_decision_threshold(
    workspace: AnnotationWorkspace,
    validation_ids: set[str],
    checkpoint_path: str | Path,
    *,
    thresholds: Sequence[float] = (
        0.30,
        0.35,
        0.40,
        0.45,
        0.50,
        0.55,
        0.60,
        0.65,
        0.70,
    ),
    device_name: str = "auto",
) -> dict[str, Any]:
    """Choose a deployment threshold only from the validation role."""

    device = _device(device_name)
    model, checkpoint = _load_model(checkpoint_path, device)
    predictions: list[tuple[np.ndarray, np.ndarray]] = []
    for item in workspace.approved_items():
        if item.sample_id not in validation_ids:
            continue
        with Image.open(item.normalized_image_path) as source:
            probabilities = _predict_original(
                model,
                source.convert("RGB"),
                image_size=int(checkpoint["training_args"]["image_size"]),
                device=device,
            )
        truth = cv2.imread(
            str(item.human_mask_path),
            cv2.IMREAD_GRAYSCALE,
        )
        if truth is None:
            raise TransferWoundSegmentationError(f"{item.sample_id}: validation mask could not be decoded")
        predictions.append((probabilities, truth > 0))
    if len(predictions) != len(validation_ids):
        raise TransferWoundSegmentationError("not every validation sample was available for calibration")

    rows: list[dict[str, float]] = []
    for threshold in thresholds:
        dice_values: list[float] = []
        iou_values: list[float] = []
        for probabilities, truth in predictions:
            predicted = clean_binary_mask((probabilities >= threshold).astype(np.uint8) * 255) > 0
            dice_values.append(binary_dice_score(predicted, truth, eps=0.0))
            iou_values.append(binary_iou_score(predicted, truth, eps=0.0))
        rows.append(
            {
                "threshold": float(threshold),
                "macro_dice": float(np.mean(dice_values)),
                "macro_iou": float(np.mean(iou_values)),
            }
        )
    selected = max(
        rows,
        key=lambda row: (
            row["macro_dice"],
            -abs(row["threshold"] - 0.5),
        ),
    )
    checkpoint["decision_threshold"] = selected["threshold"]
    checkpoint["threshold_calibration"] = {
        "role": "validation",
        "images": len(validation_ids),
        "candidates": rows,
        "selected": selected,
    }
    torch.save(checkpoint, checkpoint_path)
    return {
        "selected_threshold": selected["threshold"],
        "validation_macro_dice": selected["macro_dice"],
        "validation_macro_iou": selected["macro_iou"],
        "candidates": rows,
    }


def evaluate_lraspp_checkpoint(
    workspace: AnnotationWorkspace,
    evaluation_ids: set[str],
    checkpoint_path: str | Path,
    output_dir: str | Path,
    *,
    role: str,
    device_name: str = "auto",
    seed: int = 42,
) -> dict[str, Any]:
    """Evaluate a frozen LR-ASPP checkpoint at original resolution."""

    if role not in {"validation", "test"}:
        raise BinaryWoundValidationError("evaluation role must be validation or test")
    device = _device(device_name)
    model, checkpoint = _load_model(checkpoint_path, device)
    threshold = float(checkpoint.get("decision_threshold", 0.5))
    destination = Path(output_dir)
    prediction_dir = destination / "prediction_masks"
    overlay_dir = destination / "overlays"
    prediction_dir.mkdir(parents=True, exist_ok=True)
    overlay_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for item in workspace.approved_items():
        if item.sample_id not in evaluation_ids:
            continue
        with Image.open(item.normalized_image_path) as source:
            image = source.convert("RGB")
            image_rgb = np.asarray(image)
            probabilities = _predict_original(
                model,
                image,
                image_size=int(checkpoint["training_args"]["image_size"]),
                device=device,
            )
        prediction = clean_binary_mask((probabilities >= threshold).astype(np.uint8) * 255)
        truth_raw = cv2.imread(
            str(item.human_mask_path),
            cv2.IMREAD_GRAYSCALE,
        )
        if truth_raw is None or truth_raw.shape != prediction.shape:
            raise TransferWoundSegmentationError(f"{item.sample_id}: evaluation mask is invalid")
        truth = truth_raw > 0
        predicted = prediction > 0
        tp = int(np.logical_and(predicted, truth).sum())
        fp = int(np.logical_and(predicted, ~truth).sum())
        fn = int(np.logical_and(~predicted, truth).sum())
        tn = int(np.logical_and(~predicted, ~truth).sum())
        rows.append(
            {
                "sample_id": item.sample_id,
                "source_group": _single_source_group(workspace, item),
                "dice": binary_dice_score(predicted, truth, eps=0.0),
                "iou": binary_iou_score(predicted, truth, eps=0.0),
                "true_positive_pixels": tp,
                "false_positive_pixels": fp,
                "false_negative_pixels": fn,
                "true_negative_pixels": tn,
            }
        )
        cv2.imwrite(
            str(prediction_dir / f"{item.sample_id}.png"),
            prediction,
        )
        overlay = image_rgb.astype(np.float32).copy()
        overlay[truth] = (0.55 * overlay[truth]) + (0.45 * np.array([0, 180, 0], dtype=np.float32))
        overlay[predicted] = (0.55 * overlay[predicted]) + (0.45 * np.array([239, 68, 68], dtype=np.float32))
        Image.fromarray(
            np.clip(overlay, 0, 255).astype(np.uint8),
            mode="RGB",
        ).save(overlay_dir / f"{item.sample_id}.png")

    rows.sort(key=lambda row: row["sample_id"])
    if len(rows) != len(evaluation_ids):
        raise TransferWoundSegmentationError(f"not every {role} sample was evaluated")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["source_group"])].append(row)
    metrics = {
        "schema_version": "1.0",
        "role": role,
        "checkpoint": str(checkpoint_path),
        "checkpoint_epoch": int(checkpoint["epoch"]) + 1,
        "best_epoch": int(checkpoint["best_epoch"]),
        "decision_threshold": threshold,
        "threshold_selected_on_validation": True,
        "overall": _summarize_rows(rows, seed=seed),
        "by_source_group": {
            group: _summarize_rows(group_rows, seed=seed) for group, group_rows in sorted(grouped.items())
        },
        "clinical_status": ("experimental_requires_external_clinical_validation"),
        "predictions": str(prediction_dir),
        "overlays": str(overlay_dir),
    }
    destination.mkdir(parents=True, exist_ok=True)
    metrics_path = destination / "metrics.json"
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (destination / "per_image_metrics.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    metrics["metrics_file"] = str(metrics_path)
    return metrics


def generate_lraspp_pseudo_labels(
    workspace: AnnotationWorkspace,
    checkpoint_path: str | Path,
    config: SemiSupervisedWoundConfig,
    *,
    device_name: str = "auto",
) -> dict[str, Any]:
    """Create confidence-filtered partial masks for every unlabeled level."""

    device = _device(device_name)
    model, checkpoint = _load_model(checkpoint_path, device)
    image_size = int(checkpoint["training_args"]["image_size"])
    rows: list[dict[str, Any]] = []
    for item in workspace.unapproved_items():
        with Image.open(item.normalized_image_path) as source:
            probabilities = _predict_original(
                model,
                source.convert("RGB"),
                image_size=image_size,
                device=device,
            )
        pseudo_mask = np.full(
            probabilities.shape,
            IGNORE_INDEX,
            dtype=np.uint8,
        )
        pseudo_mask[probabilities <= config.background_threshold] = 0
        pseudo_mask[probabilities >= config.foreground_threshold] = 1
        confident = pseudo_mask != IGNORE_INDEX
        confident_ratio = float(confident.mean())
        foreground_ratio = float((pseudo_mask == 1).sum() / max(int(confident.sum()), 1))
        confidence = float(np.maximum(probabilities, 1.0 - probabilities).mean())
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
            teacher_version=str(checkpoint["model_version"]),
            accepted=accepted,
            training_eligible=True,
            suggestion_type="lraspp_confidence_filtered_pseudo_label",
        )
        rows.append(
            {
                "sample_id": item.sample_id,
                "source_group": _single_source_group(workspace, item),
                "status": "accepted" if accepted else "rejected",
                "confidence": round(confidence, 6),
                "confident_pixel_ratio": round(confident_ratio, 6),
                "foreground_ratio": round(foreground_ratio, 6),
            }
        )
    queue_path = workspace.workspace_root / "lraspp_pseudo_label_queue.csv"
    with queue_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    by_group: dict[str, dict[str, int]] = defaultdict(lambda: {"accepted": 0, "rejected": 0})
    for row in rows:
        by_group[row["source_group"]][row["status"]] += 1
    summary = {
        "teacher_version": checkpoint["model_version"],
        "unlabeled_images_processed": len(rows),
        "accepted_pseudo_labels": sum(row["status"] == "accepted" for row in rows),
        "rejected_pseudo_labels": sum(row["status"] == "rejected" for row in rows),
        "by_source_group": {group: counts for group, counts in sorted(by_group.items())},
        "review_queue": str(queue_path),
        "thresholds": {
            "background": config.background_threshold,
            "foreground": config.foreground_threshold,
            "minimum_confident_pixel_ratio": (config.minimum_confident_pixel_ratio),
        },
    }
    summary_path = workspace.workspace_root / "lraspp_pseudo_label_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary
