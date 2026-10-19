"""Reuse the bounded upload decoder and re-encode pixels without metadata."""

from __future__ import annotations

import base64
import hashlib
import io
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from src.image_quality.decoder import MAX_IMAGE_BYTES, decode_attachment


@dataclass(frozen=True)
class SanitizedImage:
    rgb: np.ndarray = field(repr=False)
    content: bytes = field(repr=False)
    content_type: str
    sha256: str
    width: int
    height: int
    metadata_removed: bool = True


def sanitize_upload(raw: bytes, content_type: str, *, consent: bool, privacy_reviewed: bool) -> SanitizedImage:
    """Strip EXIF/GPS/comments/ICC after applying orientation, before persistence.

    A visual privacy review is separately required: removing metadata cannot
    remove a face, name label or tattoo burned into the photograph.
    """
    if consent is not True or privacy_reviewed is not True:
        raise PermissionError("Confirme consentimento e revisão visual de privacidade antes de inserir a imagem.")
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_IMAGE_BYTES:
        raise ValueError("Envie uma imagem entre 1 byte e 10 MiB.")
    if content_type not in ("image/jpeg", "image/png"):
        raise ValueError("Envie uma imagem JPEG ou PNG.")
    decoded = decode_attachment({"contentType": content_type, "data": base64.b64encode(raw).decode("ascii")})
    # PNG is lossless: metrics, custody hashes and future inference use the same pixels.
    clean = Image.fromarray(decoded.rgb)
    output = io.BytesIO()
    clean.save(output, format="PNG")
    content = output.getvalue()
    return SanitizedImage(
        decoded.rgb, content, "image/png", hashlib.sha256(content).hexdigest(), decoded.width, decoded.height
    )
