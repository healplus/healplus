"""Privacy-minimized audit for binary and multiclass wound segmentation datasets."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

from .tissue_taxonomy import TissueTaxonomy

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
IMAGE_FIELD_NAMES = ("image", "image_path")
MASK_FIELD_NAMES = ("mask", "mask_path", "label_path")


@dataclass(frozen=True, slots=True)
class AuditSample:
    sample_id: str
    image_path: Path
    mask_path: Path | None
    patient_token: str | None = None
    lesion_token: str | None = None
    split: str | None = None
    device_token: str | None = None


@dataclass(frozen=True, slots=True)
class DatasetAuditConfig:
    dataset_root: Path
    image_dir: str = "images"
    mask_dir: str = "masks"
    manifest_path: Path | None = None
    small_component_ratio: float = 0.0005
    near_duplicate_distance: int = 3
    max_near_duplicate_comparisons: int = 250_000
    blur_variance_warning: float = 40.0
    exposure_ratio_warning: float = 0.30
    specular_ratio_warning: float = 0.05


def _safe_token(kind: str, value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    return hashlib.sha256(f"{kind}:{normalized}".encode()).hexdigest()[:16]


def _safe_sample_id(pair_key: str) -> str:
    return f"sample-{hashlib.sha256(pair_key.encode()).hexdigest()[:16]}"


def _first_value(record: dict[str, Any], names: Iterable[str]) -> Any:
    for name in names:
        if record.get(name) not in (None, ""):
            return record[name]
    return None


def _resolve_data_path(root: Path, value: Any) -> Path:
    path = Path(str(value or "").strip())
    return path if path.is_absolute() else root / path


def _load_manifest_records(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    if suffix == ".jsonl":
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            records = payload.get("samples") or payload.get("records")
            if isinstance(records, list):
                return [item for item in records if isinstance(item, dict)]
    raise ValueError("manifest must be CSV, JSONL, or JSON with samples/records")


def _sample_from_record(root: Path, record: dict[str, Any], index: int) -> AuditSample:
    raw_image = _first_value(record, IMAGE_FIELD_NAMES)
    raw_mask = _first_value(record, MASK_FIELD_NAMES)
    image_path = _resolve_data_path(root, raw_image)
    mask_path = _resolve_data_path(root, raw_mask) if raw_mask else None
    pair_key = str(record.get("id") or raw_image or f"manifest-row-{index}")
    return AuditSample(
        sample_id=_safe_sample_id(pair_key),
        image_path=image_path,
        mask_path=mask_path,
        patient_token=_safe_token("patient", record.get("patient_id") or record.get("patient")),
        lesion_token=_safe_token(
            "lesion",
            record.get("lesion_id") or record.get("wound_id") or record.get("case_id"),
        ),
        split=str(record.get("split") or "").strip().lower() or None,
        device_token=_safe_token("device", record.get("device_id") or record.get("device")),
    )


def _pair_key(path: Path, base: Path) -> str:
    relative = path.relative_to(base)
    stem = re.sub(r"(?i)(?:[_-](?:mask|label))$", "", relative.stem)
    return str(relative.with_name(stem)).replace("\\", "/").lower()


def discover_audit_samples(config: DatasetAuditConfig) -> tuple[list[AuditSample], list[str]]:
    root = config.dataset_root.resolve()
    if config.manifest_path:
        records = _load_manifest_records(config.manifest_path)
        return [_sample_from_record(root, record, index) for index, record in enumerate(records)], []

    image_root = root / config.image_dir
    mask_root = root / config.mask_dir
    image_paths = (
        sorted(
            path
            for path in image_root.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        if image_root.exists()
        else []
    )
    mask_paths = (
        sorted(
            path
            for path in mask_root.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        if mask_root.exists()
        else []
    )

    masks_by_key = {_pair_key(path, mask_root): path for path in mask_paths}
    samples: list[AuditSample] = []
    matched_mask_keys: set[str] = set()
    for image_path in image_paths:
        key = _pair_key(image_path, image_root)
        mask_path = masks_by_key.get(key)
        if mask_path:
            matched_mask_keys.add(key)
        samples.append(
            AuditSample(
                sample_id=_safe_sample_id(key),
                image_path=image_path,
                mask_path=mask_path,
            )
        )
    orphan_mask_ids = [
        _safe_sample_id(f"orphan-mask:{key}")
        for key in sorted(set(masks_by_key) - matched_mask_keys)
    ]
    return samples, orphan_mask_ids


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _difference_hash(path: Path) -> int:
    with Image.open(path) as image:
        gray = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        values = np.asarray(gray, dtype=np.int16)
    bits = values[:, 1:] > values[:, :-1]
    result = 0
    for bit in bits.ravel():
        result = (result << 1) | int(bit)
    return result


def _image_properties(path: Path, config: DatasetAuditConfig) -> dict[str, Any]:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError("image_decode_failed")
    if image.ndim == 2:
        channels = 1
        gray = image
        rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    else:
        channels = int(image.shape[2])
        bgr = image[:, :, :3]
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    with Image.open(path) as pil_image:
        image_format = str(pil_image.format or path.suffix.lstrip(".")).upper()
        exif = pil_image.getexif()
        has_exif = bool(exif)
        has_gps_exif = bool(exif.get(34853))

    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    blur_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    underexposed_ratio = float((gray <= 12).mean())
    overexposed_ratio = float((gray >= 243).mean())
    specular_ratio = float(((hsv[:, :, 1] <= 30) & (hsv[:, :, 2] >= 245)).mean())
    warnings: list[str] = []
    if channels not in {3, 4}:
        warnings.append("unexpected_image_channels")
    if blur_variance < config.blur_variance_warning:
        warnings.append("possible_blur")
    if underexposed_ratio > config.exposure_ratio_warning:
        warnings.append("possible_underexposure")
    if overexposed_ratio > config.exposure_ratio_warning:
        warnings.append("possible_overexposure")
    if specular_ratio > config.specular_ratio_warning:
        warnings.append("possible_specular_reflection")
    if has_gps_exif:
        warnings.append("gps_exif_present")

    return {
        "width": int(image.shape[1]),
        "height": int(image.shape[0]),
        "channels": channels,
        "format": image_format,
        "has_exif": has_exif,
        "has_gps_exif": has_gps_exif,
        "blur_variance": round(blur_variance, 4),
        "underexposed_ratio": round(underexposed_ratio, 6),
        "overexposed_ratio": round(overexposed_ratio, 6),
        "specular_ratio": round(specular_ratio, 6),
        "warnings": warnings,
    }


def _indexed_mask(mask: np.ndarray) -> tuple[np.ndarray | None, list[str]]:
    if mask.ndim == 2:
        return mask, []
    if mask.ndim == 3 and mask.shape[2] in {3, 4}:
        channels = mask[:, :, :3]
        if np.array_equal(channels[:, :, 0], channels[:, :, 1]) and np.array_equal(
            channels[:, :, 1],
            channels[:, :, 2],
        ):
            return channels[:, :, 0], ["redundant_mask_channels"]
    return None, ["mask_not_indexed_single_channel"]


def _mask_properties(
    path: Path,
    *,
    image_size: tuple[int, int] | None,
    taxonomy: TissueTaxonomy,
    config: DatasetAuditConfig,
) -> dict[str, Any]:
    raw_mask = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if raw_mask is None:
        raise ValueError("mask_decode_failed")
    mask, warnings = _indexed_mask(raw_mask)
    if mask is None:
        return {
            "width": int(raw_mask.shape[1]),
            "height": int(raw_mask.shape[0]),
            "class_values": [],
            "class_pixel_counts": {},
            "foreground_ratio": None,
            "ignore_ratio": None,
            "components_per_class": {},
            "small_components_per_class": {},
            "warnings": warnings,
        }

    values, counts = np.unique(mask, return_counts=True)
    value_counts = {int(value): int(count) for value, count in zip(values, counts)}
    allowed = set(taxonomy.allowed_mask_values)
    unexpected = sorted(set(value_counts) - allowed)
    if unexpected:
        warnings.append("unexpected_mask_values")
    if image_size and (mask.shape[1], mask.shape[0]) != image_size:
        warnings.append("image_mask_size_mismatch")

    total_pixels = int(mask.size)
    ignore_pixels = value_counts.get(taxonomy.ignore_index, 0)
    background_pixels = value_counts.get(0, 0)
    valid_pixels = max(total_pixels - ignore_pixels, 0)
    foreground_pixels = sum(
        value_counts.get(value, 0)
        for value in taxonomy.trainable_values
        if value != 0
    )
    if foreground_pixels == 0:
        warnings.append("empty_foreground_mask")
    if valid_pixels and background_pixels == 0:
        warnings.append("fully_filled_foreground_mask")

    min_component_pixels = max(4, int(total_pixels * config.small_component_ratio))
    components_per_class: dict[str, int] = {}
    small_components_per_class: dict[str, int] = {}
    for class_value in taxonomy.trainable_values:
        if class_value == 0:
            continue
        class_mask = (mask == class_value).astype(np.uint8)
        count, _, stats, _ = cv2.connectedComponentsWithStats(class_mask, connectivity=8)
        component_areas = stats[1:, cv2.CC_STAT_AREA] if count > 1 else np.array([], dtype=np.int32)
        components_per_class[str(class_value)] = int(len(component_areas))
        small_components_per_class[str(class_value)] = int((component_areas < min_component_pixels).sum())
        if len(component_areas) > 1:
            warnings.append(f"disconnected_components_class_{class_value}")
        if np.any(component_areas < min_component_pixels):
            warnings.append(f"small_components_class_{class_value}")

    return {
        "width": int(mask.shape[1]),
        "height": int(mask.shape[0]),
        "class_values": sorted(value_counts),
        "class_pixel_counts": {str(key): value for key, value in sorted(value_counts.items())},
        "foreground_ratio": round(foreground_pixels / max(valid_pixels, 1), 6),
        "ignore_ratio": round(ignore_pixels / max(total_pixels, 1), 6),
        "components_per_class": components_per_class,
        "small_components_per_class": small_components_per_class,
        "warnings": sorted(set(warnings)),
    }


def _token_split_leaks(samples: list[AuditSample], field: str) -> list[dict[str, Any]]:
    splits_by_token: dict[str, set[str]] = defaultdict(set)
    for sample in samples:
        token = getattr(sample, field)
        if token and sample.split:
            splits_by_token[token].add(sample.split)
    return [
        {"group_token": token, "splits": sorted(splits)}
        for token, splits in sorted(splits_by_token.items())
        if len(splits) > 1
    ]


def _group_size_histogram(samples: list[AuditSample], field: str) -> dict[str, int]:
    sizes = Counter(
        token
        for sample in samples
        if (token := getattr(sample, field))
    )
    return {
        str(images_per_group): group_count
        for images_per_group, group_count in sorted(Counter(sizes.values()).items())
    }


def _split_group_counts(
    samples: list[AuditSample],
    field: str,
) -> dict[str, int]:
    groups_by_split: dict[str, set[str]] = defaultdict(set)
    for sample in samples:
        token = getattr(sample, field)
        if token:
            groups_by_split[sample.split or "unassigned"].add(token)
    return {
        split: len(tokens)
        for split, tokens in sorted(groups_by_split.items())
    }


def audit_segmentation_dataset(
    config: DatasetAuditConfig,
    taxonomy: TissueTaxonomy,
) -> dict[str, Any]:
    if config.small_component_ratio <= 0:
        raise ValueError("small_component_ratio must be positive")
    if config.near_duplicate_distance < 0:
        raise ValueError("near_duplicate_distance cannot be negative")

    samples, orphan_mask_ids = discover_audit_samples(config)
    rows: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    image_hash_groups: dict[str, list[str]] = defaultdict(list)
    image_hash_by_sample: dict[str, str] = {}
    image_dhashes: list[tuple[str, int]] = []
    class_pixel_counts: Counter[int] = Counter()
    class_image_counts: Counter[int] = Counter()
    split_class_pixel_counts: dict[str, Counter[int]] = defaultdict(Counter)
    format_counts: Counter[str] = Counter()
    dimension_counts: Counter[str] = Counter()
    channel_counts: Counter[int] = Counter()
    decode_failures = 0

    for sample in samples:
        reasons: list[str] = []
        row: dict[str, Any] = {
            "sample_id": sample.sample_id,
            "split": sample.split or "",
            "has_patient_group": bool(sample.patient_token),
            "has_lesion_group": bool(sample.lesion_token),
            "has_device_group": bool(sample.device_token),
            "image_status": "missing",
            "mask_status": "missing",
        }
        image_size: tuple[int, int] | None = None
        if not sample.image_path.exists():
            reasons.append("missing_image")
        else:
            try:
                image_properties = _image_properties(sample.image_path, config)
                image_size = (image_properties["width"], image_properties["height"])
                row.update(
                    {
                        "image_status": "ok",
                        "width": image_properties["width"],
                        "height": image_properties["height"],
                        "channels": image_properties["channels"],
                        "format": image_properties["format"],
                        "blur_variance": image_properties["blur_variance"],
                        "underexposed_ratio": image_properties["underexposed_ratio"],
                        "overexposed_ratio": image_properties["overexposed_ratio"],
                        "specular_ratio": image_properties["specular_ratio"],
                        "has_exif": image_properties["has_exif"],
                        "has_gps_exif": image_properties["has_gps_exif"],
                    }
                )
                reasons.extend(image_properties["warnings"])
                format_counts[image_properties["format"]] += 1
                dimension_counts[f"{image_properties['width']}x{image_properties['height']}"] += 1
                channel_counts[image_properties["channels"]] += 1
                image_hash = _sha256(sample.image_path)
                image_hash_groups[image_hash].append(sample.sample_id)
                image_hash_by_sample[sample.sample_id] = image_hash
                image_dhashes.append((sample.sample_id, _difference_hash(sample.image_path)))
            except (OSError, UnidentifiedImageError, ValueError):
                decode_failures += 1
                reasons.append("image_decode_failed")
                row["image_status"] = "decode_failed"

        if sample.mask_path is None or not sample.mask_path.exists():
            reasons.append("missing_mask")
        else:
            try:
                mask_properties = _mask_properties(
                    sample.mask_path,
                    image_size=image_size,
                    taxonomy=taxonomy,
                    config=config,
                )
                row.update(
                    {
                        "mask_status": "ok",
                        "mask_class_values": ",".join(str(value) for value in mask_properties["class_values"]),
                        "foreground_ratio": mask_properties["foreground_ratio"],
                        "ignore_ratio": mask_properties["ignore_ratio"],
                    }
                )
                reasons.extend(mask_properties["warnings"])
                for value, count in mask_properties["class_pixel_counts"].items():
                    class_value = int(value)
                    pixel_count = int(count)
                    class_pixel_counts[class_value] += pixel_count
                    split_class_pixel_counts[sample.split or "unassigned"][class_value] += pixel_count
                    if pixel_count:
                        class_image_counts[class_value] += 1
            except (OSError, ValueError):
                decode_failures += 1
                reasons.append("mask_decode_failed")
                row["mask_status"] = "decode_failed"

        reasons = sorted(set(reasons))
        row["review_reason_codes"] = ",".join(reasons)
        row["status"] = "review" if reasons else "accepted"
        rows.append(row)
        if reasons:
            review_queue.append({"sample_id": sample.sample_id, "reason_codes": reasons})

    duplicate_groups = [
        sorted(sample_ids)
        for sample_ids in image_hash_groups.values()
        if len(sample_ids) > 1
    ]
    split_by_sample = {sample.sample_id: sample.split for sample in samples}
    cross_split_duplicate_groups = [
        group
        for group in duplicate_groups
        if len({split_by_sample.get(sample_id) for sample_id in group if split_by_sample.get(sample_id)}) > 1
    ]

    near_duplicate_pairs: list[dict[str, Any]] = []
    comparisons = 0
    comparison_limit_reached = False
    for index, (left_id, left_hash) in enumerate(image_dhashes):
        for right_id, right_hash in image_dhashes[index + 1 :]:
            comparisons += 1
            if comparisons > config.max_near_duplicate_comparisons:
                comparison_limit_reached = True
                break
            if image_hash_by_sample.get(left_id) == image_hash_by_sample.get(right_id):
                continue
            distance = (left_hash ^ right_hash).bit_count()
            if distance <= config.near_duplicate_distance:
                near_duplicate_pairs.append(
                    {
                        "left_sample_id": left_id,
                        "right_sample_id": right_id,
                        "distance": distance,
                    }
                )
        if comparison_limit_reached:
            break

    patient_leaks = _token_split_leaks(samples, "patient_token")
    lesion_leaks = _token_split_leaks(samples, "lesion_token")
    near_duplicate_cross_split = [
        pair
        for pair in near_duplicate_pairs
        if split_by_sample.get(pair["left_sample_id"])
        and split_by_sample.get(pair["right_sample_id"])
        and split_by_sample[pair["left_sample_id"]]
        != split_by_sample[pair["right_sample_id"]]
    ]
    paired_count = sum(row["image_status"] == "ok" and row["mask_status"] == "ok" for row in rows)
    patient_coverage = sum(bool(sample.patient_token) for sample in samples)
    lesion_coverage = sum(bool(sample.lesion_token) for sample in samples)

    blockers: list[str] = []
    if not samples:
        blockers.append("no_images_found")
    if paired_count == 0:
        blockers.append("no_decodable_image_mask_pairs")
    if orphan_mask_ids:
        blockers.append("masks_without_images")
    if decode_failures:
        blockers.append("undecodable_files")
    if any("unexpected_mask_values" in item["reason_codes"] for item in review_queue):
        blockers.append("unexpected_mask_values")
    if any("image_mask_size_mismatch" in item["reason_codes"] for item in review_queue):
        blockers.append("image_mask_size_mismatch")
    if patient_coverage < len(samples):
        blockers.append("patient_group_identifiers_incomplete")
    if lesion_coverage < len(samples):
        blockers.append("lesion_group_identifiers_incomplete")
    if patient_leaks:
        blockers.append("patient_split_leak")
    if lesion_leaks:
        blockers.append("lesion_split_leak")
    if cross_split_duplicate_groups:
        blockers.append("exact_duplicate_cross_split")
    if near_duplicate_cross_split:
        blockers.append("near_duplicate_cross_split_requires_review")
    if not taxonomy.clinically_validated:
        blockers.append("taxonomy_requires_clinical_validation")

    total_class_pixels = sum(
        count
        for value, count in class_pixel_counts.items()
        if value != taxonomy.ignore_index
    )
    class_distribution = {
        str(value): {
            "pixels": int(class_pixel_counts.get(value, 0)),
            "ratio": round(class_pixel_counts.get(value, 0) / max(total_class_pixels, 1), 8),
            "images": int(class_image_counts.get(value, 0)),
        }
        for value in taxonomy.allowed_mask_values
    }
    foreground_values = [value for value in taxonomy.trainable_values if value != 0]
    missing_foreground_classes = [
        value for value in foreground_values if class_pixel_counts.get(value, 0) == 0
    ]
    foreground_counts = [
        class_pixel_counts[value]
        for value in foreground_values
        if class_pixel_counts.get(value, 0) > 0
    ]
    imbalance_ratio = (
        float(max(foreground_counts) / min(foreground_counts))
        if len(foreground_counts) >= 2
        else None
    )
    if paired_count and missing_foreground_classes:
        blockers.append("trainable_foreground_classes_missing")

    split_names = sorted({sample.split or "unassigned" for sample in samples})
    split_profile = {
        split: {
            "images": sum((sample.split or "unassigned") == split for sample in samples),
            "patient_groups": _split_group_counts(samples, "patient_token").get(split, 0),
            "lesion_groups": _split_group_counts(samples, "lesion_token").get(split, 0),
            "device_groups": _split_group_counts(samples, "device_token").get(split, 0),
            "class_pixels": {
                str(value): int(split_class_pixel_counts[split].get(value, 0))
                for value in taxonomy.allowed_mask_values
            },
        }
        for split in split_names
    }

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "privacy": {
            "raw_paths_in_report": False,
            "raw_group_identifiers_in_report": False,
            "clinical_previews_generated": False,
        },
        "taxonomy": {
            "version": taxonomy.taxonomy_version,
            "status": taxonomy.status,
            "clinically_validated": taxonomy.clinically_validated,
            "ignore_index": taxonomy.ignore_index,
            "allowed_mask_values": list(taxonomy.allowed_mask_values),
        },
        "summary": {
            "images_discovered": len(samples),
            "masks_discovered": sum(sample.mask_path is not None for sample in samples) + len(orphan_mask_ids),
            "paired_decodable_samples": paired_count,
            "images_without_masks": sum(sample.mask_path is None for sample in samples),
            "masks_without_images": len(orphan_mask_ids),
            "samples_requiring_review": len(review_queue),
            "patient_group_coverage": patient_coverage,
            "lesion_group_coverage": lesion_coverage,
            "decode_failures": decode_failures,
        },
        "image_profile": {
            "formats": dict(sorted(format_counts.items())),
            "dimensions": dict(sorted(dimension_counts.items())),
            "channels": {str(key): value for key, value in sorted(channel_counts.items())},
        },
        "class_distribution": class_distribution,
        "class_balance": {
            "missing_foreground_class_values": missing_foreground_classes,
            "max_to_min_present_foreground_pixel_ratio": (
                round(imbalance_ratio, 4) if imbalance_ratio is not None else None
            ),
            "warning": (
                "high_pixel_imbalance_requires_weighting_or_sampling_review"
                if imbalance_ratio is not None and imbalance_ratio >= 10.0
                else None
            ),
        },
        "group_profiles": {
            "patient_images_per_group_histogram": _group_size_histogram(
                samples,
                "patient_token",
            ),
            "lesion_images_per_group_histogram": _group_size_histogram(
                samples,
                "lesion_token",
            ),
            "device_images_per_group_histogram": _group_size_histogram(
                samples,
                "device_token",
            ),
            "skin_tone": {
                "collected": False,
                "reason": "not_processed_without_explicit_authorized_metadata",
            },
        },
        "split_profile": split_profile,
        "mask_encoding": {
            "expected": "indexed_single_channel",
            "classes_mutually_exclusive_by_encoding": True,
            "overlap_check": "not_applicable_to_valid_indexed_masks",
        },
        "duplicates": {
            "exact_duplicate_groups": duplicate_groups,
            "cross_split_exact_duplicate_groups": cross_split_duplicate_groups,
            "near_duplicate_distance": config.near_duplicate_distance,
            "near_duplicate_pairs": near_duplicate_pairs,
            "cross_split_near_duplicate_pairs": near_duplicate_cross_split,
            "comparisons": comparisons,
            "comparison_limit_reached": comparison_limit_reached,
        },
        "split_integrity": {
            "patient_leaks": patient_leaks,
            "lesion_leaks": lesion_leaks,
        },
        "orphan_mask_ids": orphan_mask_ids,
        "release_blockers": sorted(set(blockers)),
        "samples": rows,
        "review_queue": review_queue,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    blockers = report["release_blockers"]
    class_rows = [
        f"| `{value}` | {details['pixels']} | {details['ratio']:.6f} | {details['images']} |"
        for value, details in report["class_distribution"].items()
    ]
    split_rows = [
        (
            f"| `{split}` | {details['images']} | "
            f"{details['patient_groups']} | {details['lesion_groups']} |"
        )
        for split, details in report["split_profile"].items()
    ] or ["| sem amostras | 0 | 0 | 0 |"]
    blocker_rows = [f"- `{blocker}`" for blocker in blockers] or ["- Nenhum bloqueio técnico detectado."]
    return "\n".join(
        [
            "# Auditoria do dataset de segmentação",
            "",
            f"Gerado em: `{report['generated_at']}`.",
            "",
            "O relatório usa apenas identificadores pseudônimos. Nenhum caminho, nome de paciente ou preview clínico foi persistido.",
            "",
            "## Resumo",
            "",
            f"- Imagens descobertas: {summary['images_discovered']}",
            f"- Máscaras descobertas: {summary['masks_discovered']}",
            f"- Pares decodificáveis: {summary['paired_decodable_samples']}",
            f"- Casos para revisão: {summary['samples_requiring_review']}",
            f"- Cobertura de grupo por paciente: {summary['patient_group_coverage']}/{summary['images_discovered']}",
            f"- Cobertura de grupo por ferida: {summary['lesion_group_coverage']}/{summary['images_discovered']}",
            "",
            "## Distribuição de pixels",
            "",
            "| Classe | Pixels | Proporção | Imagens |",
            "| --- | ---: | ---: | ---: |",
            *class_rows,
            "",
            "## Integridade dos splits",
            "",
            "| Split | Imagens | Grupos de paciente | Grupos de ferida |",
            "| --- | ---: | ---: | ---: |",
            *split_rows,
            "",
            "## Bloqueios para treino",
            "",
            *blocker_rows,
            "",
            "A ausência de bloqueios automáticos não equivale a validação clínica, ética ou institucional.",
            "",
        ]
    )


def _write_distribution_plot(report: dict[str, Any], output_path: Path) -> bool:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    values = list(report["class_distribution"])
    counts = [report["class_distribution"][value]["pixels"] for value in values]
    figure, axis = plt.subplots(figsize=(7, 4))
    axis.bar(values, counts, color="#0f766e")
    axis.set_title("Distribuição agregada de pixels por classe")
    axis.set_xlabel("Valor da classe")
    axis.set_ylabel("Pixels")
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)
    return True


def write_audit_outputs(report: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "segmentation_audit.json"
    samples_path = destination / "segmentation_samples.csv"
    review_path = destination / "segmentation_review_queue.csv"
    markdown_path = destination / "segmentation_audit.md"
    plot_path = destination / "class_distribution.png"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    sample_fields = sorted({key for row in report["samples"] for key in row}) or ["sample_id"]
    _write_csv(samples_path, report["samples"], sample_fields)
    review_rows = [
        {
            **row,
            "reason_codes": ",".join(row["reason_codes"]),
        }
        for row in report["review_queue"]
    ]
    _write_csv(review_path, review_rows, ["sample_id", "reason_codes"])
    markdown_path.write_text(_markdown_report(report), encoding="utf-8")
    plot_written = _write_distribution_plot(report, plot_path)

    outputs = {
        "json": str(json_path),
        "samples_csv": str(samples_path),
        "review_csv": str(review_path),
        "markdown": str(markdown_path),
    }
    if plot_written:
        outputs["class_distribution_plot"] = str(plot_path)
    return outputs
