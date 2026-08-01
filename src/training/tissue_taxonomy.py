"""Validated, versioned taxonomy for experimental wound-tissue segmentation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class TissueTaxonomyError(ValueError):
    """Raised when a taxonomy is unsafe or internally inconsistent."""


@dataclass(frozen=True, slots=True)
class TissueClassDefinition:
    value: int
    key: str
    label_pt_br: str
    trainable: bool
    color_rgb: tuple[int, int, int]
    definition: str


@dataclass(frozen=True, slots=True)
class TissueTaxonomy:
    schema_version: str
    taxonomy_version: str
    status: str
    clinically_validated: bool
    ignore_index: int
    ignore_color_rgb: tuple[int, int, int]
    classes: tuple[TissueClassDefinition, ...]
    deferred_classes: tuple[str, ...]

    @property
    def trainable_classes(self) -> tuple[TissueClassDefinition, ...]:
        return tuple(item for item in self.classes if item.trainable)

    @property
    def trainable_values(self) -> tuple[int, ...]:
        return tuple(item.value for item in self.trainable_classes)

    @property
    def allowed_mask_values(self) -> tuple[int, ...]:
        return (*self.trainable_values, self.ignore_index)

    @property
    def num_classes(self) -> int:
        return len(self.trainable_classes)


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise TissueTaxonomyError(f"{key} is required")
    return value


def _rgb_color(payload: dict[str, Any], key: str, default: tuple[int, int, int]) -> tuple[int, int, int]:
    raw_color = payload.get(key, default)
    if (
        not isinstance(raw_color, (list, tuple))
        or len(raw_color) != 3
        or any(
            not isinstance(channel, int)
            or isinstance(channel, bool)
            or not 0 <= channel <= 255
            for channel in raw_color
        )
    ):
        raise TissueTaxonomyError(f"{key} must contain three RGB integers")
    return tuple(raw_color)


def load_tissue_taxonomy(path: str | Path) -> TissueTaxonomy:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TissueTaxonomyError("taxonomy root must be an object")

    raw_classes = payload.get("classes")
    if not isinstance(raw_classes, list) or not raw_classes:
        raise TissueTaxonomyError("taxonomy classes must be a non-empty list")

    classes: list[TissueClassDefinition] = []
    for raw_class in raw_classes:
        if not isinstance(raw_class, dict):
            raise TissueTaxonomyError("each class must be an object")
        value = raw_class.get("value")
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 254:
            raise TissueTaxonomyError("class value must be an integer between 0 and 254")
        classes.append(
            TissueClassDefinition(
                value=value,
                key=_required_text(raw_class, "key"),
                label_pt_br=_required_text(raw_class, "label_pt_br"),
                trainable=bool(raw_class.get("trainable", True)),
                color_rgb=_rgb_color(raw_class, "color_rgb", (128, 128, 128)),
                definition=_required_text(raw_class, "definition"),
            )
        )

    values = [item.value for item in classes]
    keys = [item.key for item in classes]
    if len(values) != len(set(values)):
        raise TissueTaxonomyError("class values must be unique")
    if len(keys) != len(set(keys)):
        raise TissueTaxonomyError("class keys must be unique")

    ignore_index = payload.get("ignore_index")
    if not isinstance(ignore_index, int) or isinstance(ignore_index, bool) or not 0 <= ignore_index <= 255:
        raise TissueTaxonomyError("ignore_index must be an integer between 0 and 255")
    if ignore_index in values:
        raise TissueTaxonomyError("ignore_index cannot also be a class value")

    trainable_values = sorted(item.value for item in classes if item.trainable)
    if trainable_values != list(range(len(trainable_values))):
        raise TissueTaxonomyError("trainable classes must use contiguous values starting at zero")
    if not classes or classes[0].value != 0 or classes[0].key != "background":
        raise TissueTaxonomyError("class zero must be background")

    status = _required_text(payload, "status")
    clinically_validated = bool(payload.get("clinically_validated", False))
    if status == "approved" and not clinically_validated:
        raise TissueTaxonomyError("an approved taxonomy must be clinically validated")

    deferred = tuple(str(item).strip() for item in payload.get("deferred_classes", []) if str(item).strip())
    if "epithelialization" in keys and not clinically_validated:
        raise TissueTaxonomyError("epithelialization requires explicit clinical validation")

    return TissueTaxonomy(
        schema_version=_required_text(payload, "schema_version"),
        taxonomy_version=_required_text(payload, "taxonomy_version"),
        status=status,
        clinically_validated=clinically_validated,
        ignore_index=ignore_index,
        ignore_color_rgb=_rgb_color(payload, "ignore_color_rgb", (147, 51, 234)),
        classes=tuple(classes),
        deferred_classes=deferred,
    )
