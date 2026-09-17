# -*- coding: utf-8 -*-
"""Model metadata registry loader, validator, and artifact policy audit."""

from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = REPO_ROOT / "ml" / "registry" / "models.yaml"

FORBIDDEN_EXTENSIONS = {
    ".pt",
    ".pth",
    ".keras",
    ".h5",
    ".ckpt",
    ".onnx",
    ".tflite",
    ".task",
    ".pb",
    ".db",
    ".sqlite",
    ".sqlite3",
}

FORBIDDEN_DIRECTORIES = {
    "dataset",
    "models",
    "runs",
    "tmp_images",
}


@dataclass
class ModelMetadata:
    """Structured representation of a registered model entry."""

    id: str
    version: str
    status: str
    task: str
    artifact_uri: str
    local_cache_path: List[str]
    sha256: str
    license: str
    intended_use: str
    limitations: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    thresholds: Optional[Dict[str, Any]] = None
    model_card: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        data: Dict[str, Any] = {
            "id": self.id,
            "version": self.version,
            "status": self.status,
            "task": self.task,
            "artifact_uri": self.artifact_uri,
            "local_cache_path": list(self.local_cache_path),
            "sha256": self.sha256,
            "license": self.license,
            "intended_use": self.intended_use,
            "limitations": list(self.limitations),
            "metrics": dict(self.metrics),
        }
        if self.thresholds is not None:
            data["thresholds"] = self.thresholds
        if self.model_card is not None:
            data["model_card"] = self.model_card
        if self.notes is not None:
            data["notes"] = self.notes
        return data


def compute_file_sha256(file_path: Path | str, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA-256 hex digest for a file."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest().lower()


def load_model_registry(path: Path | str | None = None) -> List[ModelMetadata]:
    """Load all model metadata entries from the registry YAML."""
    registry_file = Path(path) if path else DEFAULT_REGISTRY_PATH
    if not registry_file.exists():
        raise FileNotFoundError(f"Model registry not found at {registry_file}")

    with open(registry_file, "r", encoding="utf-8") as f:
        content = yaml.safe_load(f)

    if not isinstance(content, dict) or "models" not in content:
        raise ValueError("Invalid registry format: root must contain 'models' list")

    models: List[ModelMetadata] = []
    for entry in content.get("models", []):
        if not isinstance(entry, dict):
            continue
        models.append(
            ModelMetadata(
                id=str(entry.get("id", "")),
                version=str(entry.get("version", "")),
                status=str(entry.get("status", "")),
                task=str(entry.get("task", "")),
                artifact_uri=str(entry.get("artifact_uri", "")),
                local_cache_path=list(entry.get("local_cache_path", [])),
                sha256=str(entry.get("sha256", "")),
                license=str(entry.get("license", "")),
                intended_use=str(entry.get("intended_use", "")),
                limitations=list(entry.get("limitations", [])),
                metrics=dict(entry.get("metrics", {})),
                thresholds=entry.get("thresholds"),
                model_card=entry.get("model_card"),
                notes=entry.get("notes"),
            )
        )
    return models


def validate_model_registry(registry_path: Path | str | None = None) -> List[str]:
    """Validate model registry against artifact and metadata policies.

    Returns a list of validation error messages (empty if completely valid).
    """
    errors: List[str] = []
    try:
        models = load_model_registry(registry_path)
    except Exception as exc:
        return [f"Failed to load model registry: {exc}"]

    if not models:
        return ["Model registry is empty or contains no models"]

    seen_ids = set()
    for model in models:
        prefix = f"Model '{model.id}':"
        if not model.id:
            errors.append("Encountered model entry with missing 'id'")
            continue
        if model.id in seen_ids:
            errors.append(f"{prefix} duplicate model id found in registry")
        seen_ids.add(model.id)

        # Check required string fields
        for field_name in ["version", "status", "task", "license", "intended_use", "artifact_uri", "sha256"]:
            val = getattr(model, field_name, "")
            if not val or not str(val).strip():
                errors.append(f"{prefix} missing required field '{field_name}'")

        # Check local cache paths
        if not model.local_cache_path:
            errors.append(f"{prefix} 'local_cache_path' must have at least one path")
        else:
            for cache_path in model.local_cache_path:
                normalized = Path(cache_path).as_posix()
                if normalized.startswith("/") or ".." in normalized:
                    errors.append(f"{prefix} local_cache_path '{cache_path}' must be relative to repo root")

        # Check URI safety (no credentials or embedded secrets)
        if model.artifact_uri:
            parsed = urlparse(model.artifact_uri)
            if parsed.username or parsed.password:
                errors.append(f"{prefix} artifact_uri must not contain credentials")
            if parsed.query or parsed.fragment:
                errors.append(f"{prefix} artifact_uri must not contain query strings or fragments")

        # Check limitations (must be non-empty and document constraints)
        if not model.limitations:
            errors.append(f"{prefix} 'limitations' must be a non-empty list documenting clinical and demographic bounds")
        else:
            limitations_text = " ".join(model.limitations).lower()
            if "not clinically validated" not in limitations_text and "not cleared" not in limitations_text and "reproducibility only" not in limitations_text and "auxiliary" not in limitations_text and "exploratory" not in limitations_text:
                errors.append(f"{prefix} limitations must clearly state clinical decision boundaries")

        # Check metrics
        if not model.metrics:
            errors.append(f"{prefix} missing 'metrics' mapping")

    return errors


def verify_git_artifact_cleanliness(repo_root: Path | str | None = None) -> List[str]:
    """Audit tracked Git files to guarantee no binary checkpoints or forbidden databases are in Git.

    Returns a list of violations (empty if clean).
    """
    root = Path(repo_root) if repo_root else REPO_ROOT
    violations: List[str] = []

    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=True,
        )
        tracked_files = result.stdout.splitlines()
    except Exception as exc:
        return [f"Failed to execute git ls-files: {exc}"]

    for file_path in tracked_files:
        p = Path(file_path)
        ext = p.suffix.lower()
        if ext in FORBIDDEN_EXTENSIONS:
            violations.append(f"Forbidden binary checkpoint/database tracked in Git: {file_path}")

        # Check forbidden directories
        parts = p.parts
        if len(parts) > 1 and parts[0] in FORBIDDEN_DIRECTORIES:
            # Check if it's an allowed code/doc file inside or completely forbidden
            # Per artifact-policy.md: models/, dataset/, runs/, tmp_images/ must not track blobs
            if ext in FORBIDDEN_EXTENSIONS or ext in {".bin", ".zip", ".tar", ".gz"}:
                violations.append(f"Forbidden artifact tracked in {parts[0]}/: {file_path}")

    return violations
