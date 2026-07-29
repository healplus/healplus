"""Validate the versioned runtime profile contract without installing extras."""

from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "runtime-profiles.toml"
REQUIRED_PROFILES = {"api", "web", "desktop", "ml"}
REQUIRED_PROFILE_FIELDS = {"kind", "dependency_file", "install", "run", "verify"}
API_FORBIDDEN_DEPENDENCIES = {
    "mediapipe",
    "onnxruntime-gpu",
    "open-clip-torch",
    "pyqt6",
    "tensorflow",
    "torch",
    "torchvision",
    "transformers",
    "ultralytics",
}


class RuntimeProfileError(ValueError):
    """Raised when the runtime profile manifest is incomplete or unsafe."""


def _resolve_project_path(value: str) -> Path:
    candidate = (PROJECT_ROOT / value).resolve()
    try:
        candidate.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise RuntimeProfileError(f"profile path escapes the repository: {value}") from exc
    return candidate


def _normalize_dependency(line: str) -> str | None:
    stripped = line.split("#", 1)[0].strip()
    if not stripped or stripped.startswith(("-", "--")):
        return None
    match = re.match(r"^([A-Za-z0-9_.-]+)", stripped)
    return match.group(1).lower().replace("_", "-") if match else None


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def validate_manifest(manifest: dict[str, Any], *, selected_profile: str | None = None) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    profiles = manifest.get("profiles")
    if not isinstance(profiles, dict):
        return errors + ["profiles must be a table"]

    missing_profiles = sorted(REQUIRED_PROFILES - set(profiles))
    if missing_profiles:
        errors.append(f"missing required profiles: {', '.join(missing_profiles)}")

    names = [selected_profile] if selected_profile else sorted(REQUIRED_PROFILES)
    for name in names:
        profile = profiles.get(name)
        if not isinstance(profile, dict):
            errors.append(f"profile {name!r} is not defined")
            continue

        missing_fields = sorted(REQUIRED_PROFILE_FIELDS - set(profile))
        if missing_fields:
            errors.append(f"profile {name!r} is missing: {', '.join(missing_fields)}")
            continue

        dependency_value = profile["dependency_file"]
        if not isinstance(dependency_value, str):
            errors.append(f"profile {name!r} dependency_file must be a string")
            continue

        try:
            dependency_path = _resolve_project_path(dependency_value)
        except RuntimeProfileError as exc:
            errors.append(f"profile {name!r} {exc}")
            continue
        if not dependency_path.is_file():
            errors.append(f"profile {name!r} dependency file does not exist: {dependency_value}")

        lock_value = profile.get("lock_file")
        if lock_value:
            try:
                lock_path = _resolve_project_path(str(lock_value))
            except RuntimeProfileError as exc:
                errors.append(f"profile {name!r} {exc}")
                continue
            if not lock_path.is_file():
                errors.append(f"profile {name!r} lock file does not exist: {lock_value}")

        verify = profile.get("verify")
        if not isinstance(verify, list) or not verify or not all(isinstance(command, str) and command for command in verify):
            errors.append(f"profile {name!r} verify must contain at least one command")

        if name == "api" and dependency_path.is_file():
            dependencies = {
                dependency
                for line in dependency_path.read_text(encoding="utf-8").splitlines()
                if (dependency := _normalize_dependency(line))
            }
            forbidden = sorted(dependencies & API_FORBIDDEN_DEPENDENCIES)
            if forbidden:
                errors.append(f"api profile contains optional desktop/ML dependencies: {', '.join(forbidden)}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(REQUIRED_PROFILES))
    args = parser.parse_args()

    errors = validate_manifest(load_manifest(), selected_profile=args.profile)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    scope = args.profile or "all"
    print(f"Runtime profile contract valid: {scope}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
