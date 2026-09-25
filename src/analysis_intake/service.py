"""Validate all images before atomically storing an accepted batch and its queue item."""

import base64
from dataclasses import asdict
import hashlib
from typing import Callable

from src.image_quality.assessment import ALGORITHM_VERSION, assess_image
from src.image_quality.decoder import ImageInputError, decode_attachment
from .fhir import prepare_bundle
from .repository import IntakeRepository


class IntakeService:
    def __init__(self, repository: IntakeRepository):
        self.repository = repository

    def submit(
        self,
        payload: object,
        *,
        owner_id: str,
        key: str | None,
        request_hash: str,
        resolve_patient: Callable[[str], dict],
    ) -> dict:
        bundle = prepare_bundle(payload, resolve_patient)
        replay = self.repository.replay(owner_id, key, request_hash)
        if replay:
            return replay
        images, quality = [], []
        for entry in bundle["entry"]:
            media = entry["resource"]
            if media["resourceType"] != "Media":
                continue
            attachment = {k: media["content"][k] for k in ("contentType", "data")}
            decoded = decode_attachment(attachment)
            for field in ("width", "height"):
                actual = getattr(decoded, field)
                if field in media and media[field] != actual:
                    raise ImageInputError("Dimensões Media divergem da imagem orientada.", 422)
                media[field] = actual
            raw = base64.b64decode(attachment["data"], validate=True)
            content = media["content"]
            if "size" in content and content["size"] != len(raw):
                raise ImageInputError("Media.content.size diverge dos bytes recebidos.", 422)
            if "hash" in content and content["hash"] != base64.b64encode(hashlib.sha1(raw).digest()).decode("ascii"):
                raise ImageInputError("Media.content.hash diverge dos bytes recebidos.", 422)
            content["size"] = len(raw)
            # FHIR R4 Attachment.hash is SHA-1/base64; SHA-256 remains private custody metadata.
            content["hash"] = base64.b64encode(hashlib.sha1(raw).digest()).decode("ascii")
            assessment = assess_image(decoded)
            quality.append({"mediaId": media["id"], "algorithm": ALGORITHM_VERSION, **asdict(assessment)})
            images.append(
                {
                    "id": media["id"],
                    "raw": raw,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "width": decoded.width,
                    "height": decoded.height,
                }
            )
        accepted = all(q["status"] == "accepted" for q in quality)
        if not accepted:
            # Retain the rejection decision, not a rejected photograph or a broken image URL.
            for entry in bundle["entry"]:
                if entry["resource"]["resourceType"] == "Media":
                    entry["resource"]["content"].pop("data", None)
        return self.repository.save(
            owner_id=owner_id,
            key=key,
            request_hash=request_hash,
            bundle=bundle,
            images=images,
            quality=quality,
            accepted=accepted,
        )
