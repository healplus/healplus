from __future__ import annotations

import builtins
import importlib

from scripts.check_runtime_profiles import load_manifest, validate_manifest


def test_runtime_manifest_declares_all_official_profiles():
    assert validate_manifest(load_manifest()) == []


def test_api_profile_is_valid_without_desktop_and_heavy_ml_dependencies():
    manifest = load_manifest()

    assert validate_manifest(manifest, selected_profile="api") == []
    assert manifest["profiles"]["api"]["dependency_file"] == "requirements-api.txt"


def test_headless_analyzer_import_does_not_require_pyqt(monkeypatch):
    original_import = builtins.__import__

    def reject_desktop_import(name, *args, **kwargs):
        if name == "PyQt6" or name.startswith("PyQt6."):
            raise AssertionError("headless runtime attempted to import PyQt6")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_desktop_import)
    module = importlib.import_module("src.processing.clinical_wound_analyzer_core")

    assert module.ClinicalWoundAnalyzer is not None
