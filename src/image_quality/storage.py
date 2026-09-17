# -*- coding: utf-8 -*-
"""Secure, audit-preserving storage backend for original and processed clinical images."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

DEFAULT_STORAGE_ROOT = Path("data") / "quality_storage"


@dataclass(frozen=True)
class StoredImageRef:
    """Immutable technical reference to a securely stored clinical image."""

    storage_key: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    stored_at: str
    uri: str
    transformations_applied: Tuple[str, ...] = field(default_factory=tuple)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ImageStorageBackend(ABC):
    """Abstract interface for storing raw original images with integrity audit."""

    @abstractmethod
    def save_image(
        self,
        raw_bytes: bytes,
        filename: str,
        content_type: str,
        *,
        transformations: Optional[list[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StoredImageRef:
        """Persist unaltered original image bytes and return immutable reference."""

    @abstractmethod
    def get_image(self, storage_key: str) -> Tuple[bytes, StoredImageRef]:
        """Retrieve stored image bytes and audit metadata."""


class LocalStorageBackend(ImageStorageBackend):
    """Local filesystem storage partition with sidecar audit metadata."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        raw_path = Path(base_dir) if base_dir else DEFAULT_STORAGE_ROOT
        self.base_dir = raw_path.resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_image(
        self,
        raw_bytes: bytes,
        filename: str,
        content_type: str,
        *,
        transformations: Optional[list[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StoredImageRef:
        digest = hashlib.sha256(raw_bytes).hexdigest()
        now = datetime.now(timezone.utc)
        unique_id = uuid.uuid4().hex
        ext = Path(filename).suffix.lower() or (".jpg" if content_type == "image/jpeg" else ".png")

        date_path = now.strftime("%Y/%m")
        target_dir = self.base_dir / "originals" / date_path
        target_dir.mkdir(parents=True, exist_ok=True)

        storage_key = f"{date_path}/{unique_id}{ext}"
        target_file = target_dir / f"{unique_id}{ext}"
        sidecar_file = target_dir / f"{unique_id}.meta.json"

        # Write original bytes without altering
        target_file.write_bytes(raw_bytes)

        ref = StoredImageRef(
            storage_key=storage_key,
            filename=filename,
            content_type=content_type,
            size_bytes=len(raw_bytes),
            sha256=digest,
            stored_at=now.isoformat(),
            uri=target_file.resolve().as_uri(),
            transformations_applied=tuple(transformations or []),
            metadata=dict(metadata or {}),
        )

        sidecar_file.write_text(json.dumps(ref.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return ref

    def get_image(self, storage_key: str) -> Tuple[bytes, StoredImageRef]:
        target_file = self.base_dir / "originals" / storage_key
        if not target_file.is_file():
            raise FileNotFoundError(f"Stored image not found: {storage_key}")

        sidecar_file = target_file.with_suffix(".meta.json")
        meta_dict: Dict[str, Any] = {}
        if sidecar_file.is_file():
            meta_dict = json.loads(sidecar_file.read_text(encoding="utf-8"))

        raw_bytes = target_file.read_bytes()
        ref = StoredImageRef(
            storage_key=storage_key,
            filename=meta_dict.get("filename", target_file.name),
            content_type=meta_dict.get("content_type", "image/jpeg"),
            size_bytes=len(raw_bytes),
            sha256=hashlib.sha256(raw_bytes).hexdigest(),
            stored_at=meta_dict.get("stored_at", datetime.now(timezone.utc).isoformat()),
            uri=target_file.as_uri(),
            transformations_applied=tuple(meta_dict.get("transformations_applied", [])),
            metadata=dict(meta_dict.get("metadata", {})),
        )
        return raw_bytes, ref


def get_storage_backend(base_dir: Path | str | None = None) -> ImageStorageBackend:
    """Factory for image storage backend, respecting environment configuration."""
    storage_type = os.getenv("QUALITY_STORAGE_TYPE", "local").strip().lower()
    custom_dir = base_dir or os.getenv("QUALITY_STORAGE_PATH")
    if storage_type == "local" or not os.getenv("QUALITY_STORAGE_BUCKET"):
        return LocalStorageBackend(custom_dir)

    # Could be extended for S3 / GCS bucket
    return LocalStorageBackend(custom_dir)
