"""Validated image-coordinate ROIs and morphological *proxies* of the clinical triad.

Coordinates are half-open ``(left, top, right, bottom)`` in the original RGB
image. A contextual margin is 25% of each box dimension on **each** side.
Morphology describes geometry only; it does not establish clinical boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Iterable

import cv2
import numpy as np
from numpy.typing import NDArray


MAX_IMAGE_PIXELS = 12_000_000
MAX_RESULT_PIXELS = 16_000_000
MAX_CONTEXT_PIXELS = 2_000_000
_RESOLUTION_GUIDANCE = "Reduza a resolução preservando a escala e registre a transformação no manifesto."


@dataclass(frozen=True)
class ROI:
    id: str
    bbox: tuple[int, int, int, int]
    confidence: float = 1.0
    source: str = "manual"

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", self.id):
            raise ValueError("ROI requires a pseudonymous identifier of 1–80 safe characters")
        if len(self.bbox) != 4 or any(type(v) is not int for v in self.bbox):
            raise ValueError("ROI coordinates must be four integers")
        x1, y1, x2, y2 = self.bbox
        if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1:
            raise ValueError("ROI must have positive area and nonnegative coordinates")
        if not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("ROI confidence must be in [0, 1]")
        if self.source not in {"manual", "assisted", "detector"}:
            raise ValueError("Unsupported ROI source")

    def validate_shape(self, shape: tuple[int, ...]) -> None:
        if len(shape) < 2 or self.bbox[2] > shape[1] or self.bbox[3] > shape[0]:
            raise ValueError("ROI extends beyond the original image")

    def mask(self, shape: tuple[int, ...]) -> NDArray[np.bool_]:
        self.validate_shape(shape)
        result = np.zeros(shape[:2], dtype=bool)
        x1, y1, x2, y2 = self.bbox
        result[y1:y2, x1:x2] = True
        return result

    def expanded_bbox(self, shape: tuple[int, ...], margin: float = 0.25) -> tuple[int, int, int, int]:
        self.validate_shape(shape)
        if not math.isfinite(margin) or not 0 <= margin <= 2:
            raise ValueError("Context margin must be finite and in [0, 2]")
        x1, y1, x2, y2 = self.bbox
        dx, dy = math.ceil((x2 - x1) * margin), math.ceil((y2 - y1) * margin)
        return max(0, x1 - dx), max(0, y1 - dy), min(shape[1], x2 + dx), min(shape[0], y2 + dy)


@dataclass(frozen=True)
class TriadZones:
    bed: NDArray[np.bool_]
    border: NDArray[np.bool_]
    perilesional: NDArray[np.bool_]
    provenance: str = "geometric_proxy_requires_professional_review"


def validate_rgb(image: NDArray[np.uint8]) -> None:
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Expected an RGB uint8 image with shape H×W×3")
    if min(image.shape[:2]) < 8:
        raise ValueError("Image dimensions must be at least 8×8")
    if image.shape[0] * image.shape[1] > MAX_IMAGE_PIXELS:
        raise ValueError("A imagem excede o limite de 12 megapixels. " + _RESOLUTION_GUIDANCE)


def triad_zones(bed_mask: NDArray[np.bool_], radius: int = 3) -> TriadZones:
    """Return exclusive geometric core, transition ring and surrounding skin.

    An empty bed yields empty zones. An annotation/reference bed is never
    reconstructed from colour. Rings are clipped naturally to image bounds.
    """
    if bed_mask.ndim != 2 or bed_mask.dtype != np.bool_:
        raise ValueError("Bed mask must be a two-dimensional boolean array")
    if not isinstance(radius, int) or not 1 <= radius <= 128:
        raise ValueError("Triad radius must be an integer in [1, 128]")
    bed = bed_mask.astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
    inner = cv2.erode(bed, kernel, borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
    outer = cv2.dilate(bed, kernel).astype(bool)
    surround = cv2.dilate(bed, kernel, iterations=3).astype(bool)
    return TriadZones(inner, outer & ~inner, surround & ~outer)


class ROIHandler:
    def __init__(self, context_margin: float = 0.25) -> None:
        if not math.isfinite(context_margin) or not 0 <= context_margin <= 2:
            raise ValueError("Invalid context margin")
        self.context_margin = context_margin

    def validate(self, image: NDArray[np.uint8], rois: Iterable[ROI]) -> list[ROI]:
        validate_rgb(image)
        result = list(rois)
        if not result or len(result) > 100:
            raise ValueError("Provide between 1 and 100 ROIs")
        if image.shape[0] * image.shape[1] * len(result) > MAX_RESULT_PIXELS:
            raise ValueError(
                "O lote de ROIs excede o limite agregado de 16 megapixels de mapas. " + _RESOLUTION_GUIDANCE
            )
        if len({roi.id for roi in result}) != len(result):
            raise ValueError("ROI identifiers must be unique within an image")
        for roi in result:
            roi.validate_shape(image.shape)
        return result

    def crop(self, image: NDArray[np.uint8], roi: ROI) -> tuple[NDArray[np.uint8], tuple[int, int, int, int]]:
        validate_rgb(image)
        bbox = roi.expanded_bbox(image.shape, self.context_margin)
        x1, y1, x2, y2 = bbox
        if (x2 - x1) * (y2 - y1) > MAX_CONTEXT_PIXELS:
            raise ValueError("O recorte contextual excede o limite de 2 megapixels. " + _RESOLUTION_GUIDANCE)
        return image[y1:y2, x1:x2].copy(), bbox
