# -*- coding: utf-8 -*-
"""Regression tests for model metadata registry and artifact policy."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pytest
import yaml

from src.processing.model_registry import (
    DEFAULT_REGISTRY_PATH,
    FORBIDDEN_EXTENSIONS,
    ModelMetadata,
    compute_file_sha256,
    load_model_registry,
    validate_model_registry,
    verify_git_artifact_cleanliness,
)


def test_registry_file_exists_and_parses():
    """Verify that ml/registry/models.yaml exists and parses cleanly."""
    assert DEFAULT_REGISTRY_PATH.is_file(), f"Registry missing at {DEFAULT_REGISTRY_PATH}"
    models = load_model_registry()
    assert len(models) >= 5, f"Expected at least 5 registered models, found {len(models)}"


def test_registry_passes_schema_and_safety_validation():
    """Verify that all registered models conform to safety, URI, and metadata rules."""
    errors = validate_model_registry()
    assert not errors, f"Validation errors found in registry:\n" + "\n".join(errors)


def test_every_model_has_required_fields():
    """Verify every model in registry specifies required fields per artifact policy."""
    models = load_model_registry()
    required_attributes = [
        "id",
        "version",
        "status",
        "task",
        "artifact_uri",
        "local_cache_path",
        "sha256",
        "license",
        "intended_use",
        "limitations",
        "metrics",
    ]

    for model in models:
        for attr in required_attributes:
            val = getattr(model, attr)
            assert val is not None, f"Model {model.id} missing field {attr}"
            if isinstance(val, (str, list, dict)):
                assert len(val) > 0, f"Model {model.id} has empty field {attr}"


def test_models_document_limitations_and_population():
    """Verify that limitations explicitly cover non-autonomous use and evaluated population constraints."""
    models = load_model_registry()
    for model in models:
        limitations = " ".join(model.limitations).lower()
        # Must clearly indicate boundaries (e.g. not clinically validated / not autonomous / exploratory / legacy)
        assert any(
            phrase in limitations
            for phrase in [
                "not clinically validated",
                "not cleared for autonomous",
                "reproducibility only",
                "auxiliary signal",
                "exploratory",
            ]
        ), f"Model {model.id} missing clinical boundary in limitations: {model.limitations}"

        # Must explicitly note evaluated population or dataset caveats
        assert any(
            word in limitations
            for word in ["population", "demographic", "retrospective", "subgroup", "patient", "multicenter", "validation"]
        ), f"Model {model.id} missing population/demographic notes in limitations: {model.limitations}"


def test_artifact_uris_are_safe_and_have_no_credentials():
    """Verify artifact URIs do not contain credentials, tokens, or query parameters."""
    models = load_model_registry()
    for model in models:
        uri = model.artifact_uri
        assert "@" not in uri, f"Model {model.id} URI contains userinfo: {uri}"
        assert "?" not in uri, f"Model {model.id} URI contains query parameters: {uri}"
        assert "#" not in uri, f"Model {model.id} URI contains fragments: {uri}"
        assert uri.startswith(("https://", "file://", "local-only://", "pending://")), (
            f"Model {model.id} has unexpected URI scheme: {uri}"
        )


def test_no_forbidden_binary_artifacts_are_tracked_in_git():
    """Verify that no binary weight checkpoints or forbidden databases are tracked in Git."""
    violations = verify_git_artifact_cleanliness()
    assert not violations, (
        "Artifact policy violation! Prohibited binary files are tracked in Git:\n"
        + "\n".join(violations)
    )


def test_compute_file_sha256():
    """Test SHA-256 calculation utility."""
    with tempfile.NamedTemporaryFile("wb", delete=False) as f:
        f.write(b"healplus-synthetic-test-content")
        temp_path = Path(f.name)

    try:
        expected = hashlib.sha256(b"healplus-synthetic-test-content").hexdigest()
        assert compute_file_sha256(temp_path) == expected
    finally:
        temp_path.unlink(missing_ok=True)


def test_validate_model_registry_catches_malformed_entry(tmp_path):
    """Test validator catches invalid schema, missing fields, or unsafe URIs."""
    bad_yaml = tmp_path / "bad_models.yaml"
    bad_yaml.write_text(
        yaml.dump(
            {
                "models": [
                    {
                        "id": "bad-model",
                        "artifact_uri": "https://user:password@storage.example.com/model.pt",
                        "local_cache_path": [],
                        "limitations": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    errors = validate_model_registry(bad_yaml)
    assert any("missing required field" in e for e in errors)
    assert any("credentials" in e for e in errors)
    assert any("local_cache_path" in e for e in errors)
    assert any("limitations" in e for e in errors)
