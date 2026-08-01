"""Local, resumable human-in-the-loop annotation for binary wound masks."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


class GuidedAnnotationError(ValueError):
    """Raised when annotation input or output is invalid."""


@dataclass(frozen=True, slots=True)
class AnnotationItem:
    sample_id: str
    image_sha256: str
    source_path: Path
    normalized_image_path: Path
    human_mask_path: Path
    pseudo_mask_path: Path


def _natural_key(path: Path) -> list[tuple[int, str | int]]:
    return [
        (0, int(part)) if part.isdigit() else (1, part.lower())
        for part in re.split(r"(\d+)", str(path))
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def polygon_to_mask(
    shape: tuple[int, int],
    vertices: list[tuple[float, float]],
) -> np.ndarray:
    if len(vertices) < 3:
        raise GuidedAnnotationError("at least three points are required")
    height, width = shape
    points = np.rint(vertices).astype(np.int32)
    points[:, 0] = np.clip(points[:, 0], 0, width - 1)
    points[:, 1] = np.clip(points[:, 1], 0, height - 1)
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(mask, [points], 255)
    return mask


class AnnotationWorkspace:
    """Owns normalized copies, masks and a path-free progress manifest."""

    def __init__(
        self,
        image_root: str | Path,
        workspace_root: str | Path,
    ):
        self.image_root = Path(image_root).resolve()
        self.workspace_root = Path(workspace_root).resolve()
        if not self.image_root.is_dir():
            raise GuidedAnnotationError("image directory does not exist")
        self.normalized_dir = self.workspace_root / "normalized_images"
        self.human_mask_dir = self.workspace_root / "human_masks"
        self.pseudo_mask_dir = self.workspace_root / "pseudo_masks"
        self.manifest_path = self.workspace_root / "annotation_progress.json"
        self.normalized_dir.mkdir(parents=True, exist_ok=True)
        self.human_mask_dir.mkdir(parents=True, exist_ok=True)
        self.pseudo_mask_dir.mkdir(parents=True, exist_ok=True)
        self._records = self._load_records()
        self.items = self._discover_items()
        if not self.items:
            raise GuidedAnnotationError("no supported images were found")

    @classmethod
    def from_existing(cls, workspace_root: str | Path) -> "AnnotationWorkspace":
        workspace_path = Path(workspace_root).resolve()
        instance = cls.__new__(cls)
        instance.workspace_root = workspace_path
        instance.normalized_dir = workspace_path / "normalized_images"
        instance.image_root = instance.normalized_dir
        instance.human_mask_dir = workspace_path / "human_masks"
        instance.pseudo_mask_dir = workspace_path / "pseudo_masks"
        instance.manifest_path = workspace_path / "annotation_progress.json"
        if not instance.manifest_path.is_file() or not instance.normalized_dir.is_dir():
            raise GuidedAnnotationError("existing annotation workspace is incomplete")
        instance._records = instance._load_records()
        instance.items = []
        for normalized_path in sorted(
            instance.normalized_dir.glob("sample-*.png"),
            key=_natural_key,
        ):
            sample_id = normalized_path.stem
            record = instance._records.get(sample_id, {})
            image_hash = str(
                record.get("image_sha256")
                or sample_id.removeprefix("sample-")
            )
            instance.items.append(
                AnnotationItem(
                    sample_id=sample_id,
                    image_sha256=image_hash,
                    source_path=normalized_path,
                    normalized_image_path=normalized_path,
                    human_mask_path=instance.human_mask_dir / f"{sample_id}.png",
                    pseudo_mask_path=instance.pseudo_mask_dir / f"{sample_id}.png",
                )
            )
        if not instance.items:
            raise GuidedAnnotationError("existing workspace has no normalized images")
        return instance

    def _load_records(self) -> dict[str, dict[str, Any]]:
        if not self.manifest_path.is_file():
            return {}
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        records = payload.get("records", []) if isinstance(payload, dict) else []
        return {
            str(record["sample_id"]): dict(record)
            for record in records
            if isinstance(record, dict) and record.get("sample_id")
        }

    def _discover_items(self) -> list[AnnotationItem]:
        source_paths = sorted(
            (
                path
                for path in self.image_root.rglob("*")
                if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
            ),
            key=_natural_key,
        )
        items: list[AnnotationItem] = []
        seen_hashes: set[str] = set()
        for source_path in source_paths:
            image_hash = _sha256(source_path)
            if image_hash in seen_hashes:
                continue
            seen_hashes.add(image_hash)
            sample_id = f"sample-{image_hash[:16]}"
            items.append(
                AnnotationItem(
                    sample_id=sample_id,
                    image_sha256=image_hash,
                    source_path=source_path,
                    normalized_image_path=self.normalized_dir / f"{sample_id}.png",
                    human_mask_path=self.human_mask_dir / f"{sample_id}.png",
                    pseudo_mask_path=self.pseudo_mask_dir / f"{sample_id}.png",
                )
            )
        return items

    def _write_manifest(self) -> None:
        payload = {
            "schema_version": "1.0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "privacy": {
                "raw_source_paths_stored": False,
                "raw_identifiers_stored": False,
                "normalized_images_have_exif": False,
            },
            "records": [
                self._records[sample_id]
                for sample_id in sorted(self._records)
            ],
        }
        temporary_path = self.manifest_path.with_suffix(".json.tmp")
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(self.manifest_path)

    def ensure_normalized_image(self, item: AnnotationItem) -> Path:
        if item.normalized_image_path.is_file():
            return item.normalized_image_path
        try:
            with Image.open(item.source_path) as source:
                normalized = ImageOps.exif_transpose(source).convert("RGB")
                normalized.save(item.normalized_image_path, format="PNG")
        except (OSError, UnidentifiedImageError) as exc:
            raise GuidedAnnotationError(
                f"{item.sample_id}: image could not be normalized"
            ) from exc
        return item.normalized_image_path

    def load_image_rgb(self, item: AnnotationItem) -> np.ndarray:
        path = self.ensure_normalized_image(item)
        try:
            with Image.open(path) as image:
                return np.asarray(image.convert("RGB"))
        except (OSError, UnidentifiedImageError) as exc:
            raise GuidedAnnotationError(
                f"{item.sample_id}: normalized image could not be decoded"
            ) from exc

    def load_editable_mask(self, item: AnnotationItem) -> tuple[np.ndarray, str]:
        image = self.load_image_rgb(item)
        record = self._records.get(item.sample_id, {})
        if item.human_mask_path.is_file():
            raw = cv2.imread(str(item.human_mask_path), cv2.IMREAD_GRAYSCALE)
            source = str(record.get("provenance") or "human")
            binary = raw > 0 if raw is not None else None
        elif item.pseudo_mask_path.is_file():
            raw = cv2.imread(str(item.pseudo_mask_path), cv2.IMREAD_GRAYSCALE)
            source = "pseudo_suggestion"
            binary = raw == 1 if raw is not None else None
        else:
            return np.zeros(image.shape[:2], dtype=np.uint8), "empty"
        if raw is None or raw.shape != image.shape[:2]:
            raise GuidedAnnotationError(
                f"{item.sample_id}: saved mask is invalid"
            )
        return binary.astype(np.uint8) * 255, source

    def save_human_mask(
        self,
        item: AnnotationItem,
        mask: np.ndarray,
        *,
        status: str,
        provenance: str,
    ) -> None:
        image = self.load_image_rgb(item)
        if mask.ndim != 2 or mask.shape != image.shape[:2]:
            raise GuidedAnnotationError("mask must match normalized image dimensions")
        binary = (mask > 0).astype(np.uint8) * 255
        if status == "approved":
            coverage = float((binary > 0).mean())
            if not 0.0005 <= coverage <= 0.95:
                raise GuidedAnnotationError(
                    "approved mask must cover between 0.05% and 95% of the image"
                )
        if not cv2.imwrite(str(item.human_mask_path), binary):
            raise GuidedAnnotationError("mask could not be saved")
        self._records[item.sample_id] = {
            "sample_id": item.sample_id,
            "image_sha256": item.image_sha256,
            "normalized_image": f"normalized_images/{item.sample_id}.png",
            "human_mask": f"human_masks/{item.sample_id}.png",
            "status": status,
            "provenance": provenance,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._write_manifest()

    def register_pseudo_mask(
        self,
        item: AnnotationItem,
        *,
        confidence: float,
        confident_pixel_ratio: float,
        foreground_ratio: float,
        teacher_version: str,
        accepted: bool,
        training_eligible: bool = True,
        suggestion_type: str = "confidence_filtered_pseudo_label",
    ) -> None:
        record = dict(self._records.get(item.sample_id, {}))
        record.update(
            {
                "sample_id": item.sample_id,
                "image_sha256": item.image_sha256,
                "normalized_image": f"normalized_images/{item.sample_id}.png",
                "pseudo_mask": f"pseudo_masks/{item.sample_id}.png",
                "status": "pseudo_pending_review" if accepted else "pseudo_rejected",
                "pseudo_confidence": round(confidence, 6),
                "confident_pixel_ratio": round(confident_pixel_ratio, 6),
                "foreground_ratio": round(foreground_ratio, 6),
                "teacher_version": teacher_version,
                "pseudo_training_eligible": bool(accepted and training_eligible),
                "suggestion_type": suggestion_type,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._records[item.sample_id] = record
        self._write_manifest()

    def record(self, sample_id: str) -> dict[str, Any]:
        return dict(self._records.get(sample_id, {}))

    def approved_items(self) -> list[AnnotationItem]:
        return [
            item
            for item in self.items
            if self._records.get(item.sample_id, {}).get("status") == "approved"
            and item.human_mask_path.is_file()
        ]

    def unapproved_items(self) -> list[AnnotationItem]:
        approved = {item.sample_id for item in self.approved_items()}
        return [item for item in self.items if item.sample_id not in approved]

    @property
    def approved_count(self) -> int:
        return len(self.approved_items())

    @property
    def pseudo_pending_count(self) -> int:
        return sum(
            record.get("status") == "pseudo_pending_review"
            for record in self._records.values()
        )


class GuidedAnnotationApp:
    """Matplotlib lasso UI: circle, approve, automatically advance."""

    def __init__(
        self,
        workspace: AnnotationWorkspace,
        *,
        target_approved: int = 100,
        prefer_pseudo_suggestions: bool = False,
    ):
        import matplotlib.pyplot as plt
        from matplotlib.widgets import Button, LassoSelector

        if target_approved <= 0:
            raise GuidedAnnotationError("target_approved must be positive")
        if target_approved > len(workspace.items):
            raise GuidedAnnotationError(
                f"target requires {target_approved} images, but only "
                f"{len(workspace.items)} unique images were found"
            )
        self.workspace = workspace
        self.target_approved = target_approved
        self.items = list(workspace.items)
        if prefer_pseudo_suggestions:
            self.items.sort(
                key=lambda item: (
                    workspace.record(item.sample_id).get("status")
                    != "pseudo_pending_review",
                    float(
                        workspace.record(item.sample_id).get(
                            "pseudo_confidence",
                            1.0,
                        )
                    ),
                    item.sample_id,
                )
            )
        self.index = self._first_unapproved_index()
        self.mask: np.ndarray | None = None
        self.original_mask: np.ndarray | None = None
        self.image_rgb: np.ndarray | None = None
        self.mask_source = "empty"
        self.mode = "add"
        self.undo_stack: list[np.ndarray] = []
        self.completed = workspace.approved_count >= self.target_approved
        self.plt = plt

        self.figure, self.axes = plt.subplots(1, 3, figsize=(15, 7))
        self.figure.subplots_adjust(bottom=0.19, top=0.88, wspace=0.08)
        self.lasso = LassoSelector(
            self.axes[0],
            onselect=self._on_lasso,
            button=1,
            useblit=True,
        )
        button_specs = [
            ("Adicionar", 0.03, self._set_add),
            ("Apagar", 0.14, self._set_erase),
            ("Desfazer", 0.25, self._undo),
            ("Limpar", 0.36, self._clear),
            ("Anterior", 0.47, self._previous),
            ("Pendente", 0.58, self._pending_next),
            ("Aprovar e próxima", 0.70, self._approve_next),
        ]
        self.buttons = []
        for label, left, callback in button_specs:
            width = 0.10 if label != "Aprovar e próxima" else 0.25
            axis = self.figure.add_axes([left, 0.055, width, 0.07])
            button = Button(axis, label)
            button.on_clicked(callback)
            self.buttons.append(button)
        self.figure.canvas.mpl_connect("key_press_event", self._on_key)
        self._load_current()

    def _first_unapproved_index(self) -> int:
        for index, item in enumerate(self.workspace.items):
            if self.workspace.record(item.sample_id).get("status") != "approved":
                return index
        return 0

    def _load_current(self) -> None:
        item = self.items[self.index]
        self.image_rgb = self.workspace.load_image_rgb(item)
        self.mask, self.mask_source = self.workspace.load_editable_mask(item)
        self.original_mask = self.mask.copy()
        self.undo_stack = []
        self._draw()

    def _draw(self, message: str = "") -> None:
        for axis in self.axes:
            axis.clear()
            axis.axis("off")
        self.axes[0].imshow(self.image_rgb)
        self.axes[0].set_title("Contorne a ferida nesta imagem")
        self.axes[1].imshow(self.mask, cmap="gray", vmin=0, vmax=255)
        self.axes[1].set_title("Máscara")
        overlay = self.image_rgb.astype(np.float32).copy()
        selected = self.mask > 0
        overlay[selected] = (0.55 * overlay[selected]) + (
            0.45 * np.array([239, 68, 68], dtype=np.float32)
        )
        self.axes[2].imshow(np.clip(overlay, 0, 255).astype(np.uint8))
        self.axes[2].set_title("Overlay")
        item = self.items[self.index]
        status = self.workspace.record(item.sample_id).get("status", "novo")
        title = (
            f"Imagem {self.index + 1}/{len(self.items)} | "
            f"aprovadas {self.workspace.approved_count}/{self.target_approved} | "
            f"modo={self.mode} | origem={self.mask_source} | status={status}"
        )
        if message:
            title += f" | {message}"
        self.figure.suptitle(title)
        self.figure.canvas.draw_idle()

    def _on_lasso(self, vertices: list[tuple[float, float]]) -> None:
        if self.mask is None:
            return
        try:
            selected = polygon_to_mask(self.mask.shape, vertices)
        except GuidedAnnotationError:
            self._draw("contorno muito pequeno")
            return
        self.undo_stack.append(self.mask.copy())
        if self.mode == "erase":
            self.mask[selected > 0] = 0
        else:
            self.mask[selected > 0] = 255
        self._draw()

    def _set_add(self, _event=None) -> None:
        self.mode = "add"
        self._draw()

    def _set_erase(self, _event=None) -> None:
        self.mode = "erase"
        self._draw()

    def _undo(self, _event=None) -> None:
        if self.undo_stack:
            self.mask = self.undo_stack.pop()
            self._draw()

    def _clear(self, _event=None) -> None:
        self.undo_stack.append(self.mask.copy())
        self.mask.fill(0)
        self._draw()

    def _save_current(self, *, status: str) -> bool:
        item = self.items[self.index]
        provenance = (
            "human_reviewed_pseudo"
            if self.mask_source in {"pseudo_suggestion", "human_reviewed_pseudo"}
            else "human_manual"
        )
        try:
            self.workspace.save_human_mask(
                item,
                self.mask,
                status=status,
                provenance=provenance,
            )
        except GuidedAnnotationError as exc:
            self._draw(str(exc))
            return False
        return True

    def _advance_to_next_unapproved(self) -> None:
        for offset in range(1, len(self.items) + 1):
            candidate = (self.index + offset) % len(self.items)
            item = self.items[candidate]
            if self.workspace.record(item.sample_id).get("status") != "approved":
                self.index = candidate
                self._load_current()
                return
        self.completed = True
        self.plt.close(self.figure)

    def _approve_next(self, _event=None) -> None:
        if not self._save_current(status="approved"):
            return
        if self.workspace.approved_count >= self.target_approved:
            self.completed = True
            self.plt.close(self.figure)
            return
        self._advance_to_next_unapproved()

    def _pending_next(self, _event=None) -> None:
        if self.mask is not None and np.any(self.mask > 0):
            self._save_current(status="pending")
        self._advance_to_next_unapproved()

    def _previous(self, _event=None) -> None:
        self.index = (self.index - 1) % len(self.items)
        self._load_current()

    def _on_key(self, event) -> None:
        if event.key == "a":
            self._approve_next()
        elif event.key == "e":
            self._set_erase()
        elif event.key in {"insert", "+"}:
            self._set_add()
        elif event.key in {"ctrl+z", "backspace"}:
            self._undo()
        elif event.key in {"right", "n"}:
            self._pending_next()
        elif event.key == "left":
            self._previous()
        elif event.key in {"q", "escape"}:
            self.plt.close(self.figure)

    def run(self) -> bool:
        if self.completed:
            return True
        self.plt.show()
        return self.workspace.approved_count >= self.target_approved
