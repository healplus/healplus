"""Build a path-free training workspace from reviewed annotation workspaces."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from .guided_wound_annotation import (
    IMAGE_EXTENSIONS,
    AnnotationWorkspace,
    GuidedAnnotationError,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _approved_masks_by_hash(
    workspace_roots: Sequence[str | Path],
) -> dict[str, Path]:
    approved: dict[str, Path] = {}
    for workspace_root in workspace_roots:
        workspace = AnnotationWorkspace.from_existing(workspace_root)
        for item in workspace.approved_items():
            existing = approved.get(item.image_sha256)
            if existing is None:
                approved[item.image_sha256] = item.human_mask_path
                continue
            first = cv2.imread(str(existing), cv2.IMREAD_GRAYSCALE)
            second = cv2.imread(str(item.human_mask_path), cv2.IMREAD_GRAYSCALE)
            if (
                first is None
                or second is None
                or first.shape != second.shape
                or not np.array_equal(first > 0, second > 0)
            ):
                raise GuidedAnnotationError(f"conflicting reviewed masks for image {item.image_sha256[:16]}")
    return approved


def build_combined_workspace(
    image_groups: Mapping[str, str | Path],
    reviewed_workspace_roots: Sequence[str | Path],
    output_root: str | Path,
) -> dict[str, Any]:
    """Normalize grouped images and import reviewed masks without raw paths."""

    if not image_groups:
        raise GuidedAnnotationError("at least one image group is required")
    output = Path(output_root).resolve()
    manifest_path = output / "annotation_progress.json"
    if manifest_path.exists():
        raise GuidedAnnotationError("combined workspace already exists")

    normalized_dir = output / "normalized_images"
    human_mask_dir = output / "human_masks"
    pseudo_mask_dir = output / "pseudo_masks"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    human_mask_dir.mkdir(parents=True, exist_ok=True)
    pseudo_mask_dir.mkdir(parents=True, exist_ok=True)

    approved_masks = _approved_masks_by_hash(reviewed_workspace_roots)
    discovered: dict[str, dict[str, Any]] = {}
    sample_ids: dict[str, str] = {}
    input_image_count = 0

    for group, root_value in sorted(image_groups.items()):
        root = Path(root_value).resolve()
        if not root.is_dir():
            raise GuidedAnnotationError(f"image group does not exist: {group}")
        source_paths = sorted(
            path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        if not source_paths:
            raise GuidedAnnotationError(f"image group is empty: {group}")
        for source_path in source_paths:
            input_image_count += 1
            image_hash = _sha256(source_path)
            sample_id = f"sample-{image_hash[:16]}"
            collision_hash = sample_ids.get(sample_id)
            if collision_hash is not None and collision_hash != image_hash:
                raise GuidedAnnotationError(f"sample identifier collision: {sample_id}")
            sample_ids[sample_id] = image_hash
            if image_hash in discovered:
                discovered[image_hash]["source_groups"].add(group)
                continue

            normalized_path = normalized_dir / f"{sample_id}.png"
            try:
                with Image.open(source_path) as source:
                    normalized = ImageOps.exif_transpose(source).convert("RGB")
                    normalized.save(normalized_path, format="PNG")
            except (OSError, UnidentifiedImageError) as exc:
                raise GuidedAnnotationError(f"{sample_id}: image could not be normalized") from exc
            discovered[image_hash] = {
                "sample_id": sample_id,
                "image_sha256": image_hash,
                "source_groups": {group},
            }

    records: list[dict[str, Any]] = []
    approved_count = 0
    for image_hash, discovered_record in sorted(discovered.items()):
        sample_id = discovered_record["sample_id"]
        mask_source = approved_masks.get(image_hash)
        record = {
            "sample_id": sample_id,
            "image_sha256": image_hash,
            "normalized_image": f"normalized_images/{sample_id}.png",
            "source_groups": sorted(discovered_record["source_groups"]),
            "status": "unlabeled",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if mask_source is not None:
            destination = human_mask_dir / f"{sample_id}.png"
            shutil.copy2(mask_source, destination)
            record.update(
                {
                    "human_mask": f"human_masks/{sample_id}.png",
                    "status": "approved",
                    "provenance": "human_reviewed_import",
                }
            )
            approved_count += 1
        records.append(record)

    manifest = {
        "schema_version": "1.0",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "privacy": {
            "raw_source_paths_stored": False,
            "raw_identifiers_stored": False,
            "normalized_images_have_exif": False,
        },
        "source_groups": sorted(image_groups),
        "records": records,
    }
    temporary_path = manifest_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(manifest_path)

    return {
        "workspace": str(output),
        "source_groups": sorted(image_groups),
        "unique_images": len(discovered),
        "approved_human_masks": approved_count,
        "unlabeled_images": len(discovered) - approved_count,
        "duplicate_images_removed": input_image_count - len(discovered),
    }
