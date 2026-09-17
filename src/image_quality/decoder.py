"""Bounded decoding of untrusted uploads, without retaining image metadata."""

from __future__ import annotations

import base64
import binascii
import io
from dataclasses import dataclass
from typing import cast

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 12_000_000
MAX_REQUEST_BYTES = 14 * 1024 * 1024


class ImageInputError(ValueError):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class DecodedImage:
    rgb: np.ndarray
    width: int
    height: int
    monochrome: bool


def decode_attachment(attachment: object) -> DecodedImage:
    if not isinstance(attachment, dict) or set(attachment) != {"contentType", "data"}:
        raise ImageInputError("Envie somente contentType e data no Attachment; URLs não são aceitas.")
    mime = attachment["contentType"]
    if mime not in ("image/jpeg", "image/png"):
        raise ImageInputError("Envie uma imagem JPEG ou PNG.", 415)
    encoded = attachment["data"]
    if not isinstance(encoded, str) or not encoded:
        raise ImageInputError("Preencha data com a imagem em base64.")
    if len(encoded) > 4 * ((MAX_IMAGE_BYTES + 2) // 3):
        raise ImageInputError("A imagem deve ter no máximo 10 MiB.", 413)
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ImageInputError("O conteúdo base64 é inválido.") from None
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ImageInputError("A imagem deve conter entre 1 byte e 10 MiB.", 413)

    try:
        with Image.open(io.BytesIO(raw)) as probe:
            expected_format = "JPEG" if mime == "image/jpeg" else "PNG"
            if probe.format != expected_format:
                raise ImageInputError("O tipo declarado não corresponde à imagem.", 415)
            # Check dimensions BEFORE verify/load/transposition allocates decoded pixels.
            width, height = probe.size
            if width * height > MAX_IMAGE_PIXELS:
                raise ImageInputError("A imagem deve ter no máximo 12 megapixels.", 413)
            if min(width, height) < 16:
                raise ImageInputError("A imagem deve ter pelo menos 16 pixels em cada dimensão.", 422)
            if getattr(probe, "n_frames", 1) != 1:
                raise ImageInputError("Envie uma imagem estática com um único quadro.", 415)
            if probe.mode not in {"RGB", "RGBA", "L", "LA", "P"}:
                raise ImageInputError("Converta a imagem para RGB de 8 bits antes do envio.", 415)
            probe.verify()
        with Image.open(io.BytesIO(raw)) as source:
            source.load()
            oriented = ImageOps.exif_transpose(source)
            if "A" in oriented.getbands() or "transparency" in oriented.info:
                alpha_minimum = cast(int, oriented.convert("RGBA").getchannel("A").getextrema()[0])
                if alpha_minimum < 255:
                    raise ImageInputError("Envie uma fotografia sem áreas transparentes.", 422)
            rgb = np.array(oriented.convert("RGB"), dtype=np.uint8)
            monochrome = bool(np.array_equal(rgb[:, :, 0], rgb[:, :, 1]) and np.array_equal(rgb[:, :, 1], rgb[:, :, 2]))
            return DecodedImage(rgb, oriented.width, oriented.height, monochrome)
    except ImageInputError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ImageInputError("A imagem excede o limite seguro de resolução.", 413) from None
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise ImageInputError("Não foi possível decodificar a imagem; envie um JPEG ou PNG íntegro.", 422) from None
