"""Local-only visual review helpers for indexed wound segmentation masks."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from .segmentation_audit import AuditSample
from .tissue_taxonomy import TissueTaxonomy


class MaskReviewError(ValueError):
    """Raised when a review sample cannot be rendered safely."""


@dataclass(frozen=True, slots=True)
class ReviewImage:
    sample_id: str
    image_rgb: np.ndarray
    mask: np.ndarray
    color_mask_rgb: np.ndarray
    overlay_rgb: np.ndarray


def read_indexed_mask(path: Path) -> np.ndarray:
    try:
        with Image.open(path) as source:
            mask = np.asarray(source)
    except (OSError, UnidentifiedImageError) as exc:
        raise MaskReviewError("mask could not be decoded") from exc

    if mask.ndim == 2:
        return mask.astype(np.uint8, copy=False)
    if mask.ndim == 3 and mask.shape[2] in {3, 4}:
        channels = mask[:, :, :3]
        if np.array_equal(channels[:, :, 0], channels[:, :, 1]) and np.array_equal(
            channels[:, :, 1],
            channels[:, :, 2],
        ):
            return channels[:, :, 0].astype(np.uint8, copy=False)
    raise MaskReviewError("mask must be an indexed single-channel image")


def colorize_indexed_mask(
    mask: np.ndarray,
    taxonomy: TissueTaxonomy,
) -> np.ndarray:
    if mask.ndim != 2:
        raise MaskReviewError("mask must have shape H x W")
    color_mask = np.full((*mask.shape, 3), (255, 0, 255), dtype=np.uint8)
    for class_definition in taxonomy.classes:
        color_mask[mask == class_definition.value] = class_definition.color_rgb
    color_mask[mask == taxonomy.ignore_index] = taxonomy.ignore_color_rgb
    return color_mask


def create_mask_overlay(
    image_rgb: np.ndarray,
    mask: np.ndarray,
    taxonomy: TissueTaxonomy,
    *,
    alpha: float = 0.45,
) -> np.ndarray:
    if image_rgb.ndim != 3 or image_rgb.shape[2] != 3:
        raise MaskReviewError("image must have shape H x W x 3")
    if image_rgb.shape[:2] != mask.shape:
        raise MaskReviewError("image and mask must have the same spatial size")
    if not 0.0 <= alpha <= 1.0:
        raise MaskReviewError("alpha must be between zero and one")

    color_mask = colorize_indexed_mask(mask, taxonomy)
    overlay = image_rgb.astype(np.float32).copy()
    visible = mask != 0
    overlay[visible] = (
        (1.0 - alpha) * overlay[visible]
        + alpha * color_mask[visible].astype(np.float32)
    )
    return np.clip(overlay, 0, 255).astype(np.uint8)


def load_review_image(
    sample: AuditSample,
    taxonomy: TissueTaxonomy,
    *,
    alpha: float = 0.45,
) -> ReviewImage:
    if sample.mask_path is None:
        raise MaskReviewError("sample has no mask")
    try:
        with Image.open(sample.image_path) as source:
            image_rgb = np.asarray(ImageOps.exif_transpose(source).convert("RGB"))
    except (OSError, UnidentifiedImageError) as exc:
        raise MaskReviewError("image could not be decoded") from exc

    mask = read_indexed_mask(sample.mask_path)
    unexpected = sorted(set(np.unique(mask).tolist()) - set(taxonomy.allowed_mask_values))
    if unexpected:
        raise MaskReviewError("mask contains values outside the active taxonomy")
    color_mask = colorize_indexed_mask(mask, taxonomy)
    overlay = create_mask_overlay(image_rgb, mask, taxonomy, alpha=alpha)
    return ReviewImage(
        sample_id=sample.sample_id,
        image_rgb=image_rgb,
        mask=mask,
        color_mask_rgb=color_mask,
        overlay_rgb=overlay,
    )


def write_review_decisions(
    output_path: str | Path,
    decisions: Iterable[dict[str, str]],
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["sample_id", "review_status", "reason_code"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for decision in decisions:
            writer.writerow(decision)
    return path
