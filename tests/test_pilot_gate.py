from __future__ import annotations

import copy
from pathlib import Path

from scripts.validate_pilot_gate import load_manifest, validate_manifest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CURRENT_MANIFEST = (
    PROJECT_ROOT
    / "docs"
    / "operations"
    / "release-evidence"
    / "pilot-readiness-2026-07-27.json"
)


def test_current_no_go_manifest_is_structurally_valid():
    manifest = load_manifest(CURRENT_MANIFEST)

    assert validate_manifest(manifest) == []


def test_current_no_go_manifest_cannot_authorize_release():
    manifest = load_manifest(CURRENT_MANIFEST)

    errors = validate_manifest(manifest, require_go=True)

    assert "release requires decision.outcome GO" in errors
    assert any("release blocked by non-passing P0 gates" in error for error in errors)
    assert any("release requires approved roles" in error for error in errors)


def test_go_decision_cannot_hide_a_blocked_p0():
    manifest = copy.deepcopy(load_manifest(CURRENT_MANIFEST))
    manifest["decision"]["outcome"] = "GO"

    errors = validate_manifest(manifest)

    assert any("release blocked by non-passing P0 gates" in error for error in errors)


def test_missing_local_evidence_is_rejected():
    manifest = copy.deepcopy(load_manifest(CURRENT_MANIFEST))
    manifest["gates"][0]["evidence"] = ["docs/does-not-exist.md"]

    errors = validate_manifest(manifest)

    assert any("evidence path does not exist" in error for error in errors)


def test_release_candidate_and_notes_must_match_expected_values():
    manifest = load_manifest(CURRENT_MANIFEST)

    errors = validate_manifest(
        manifest,
        expected_candidate="v9.9.9",
        expected_release_notes="docs/operations/releases/v9.9.9.md",
    )

    assert "candidate must match 'v9.9.9'" in errors
    assert "release_notes must match 'docs/operations/releases/v9.9.9.md'" in errors


def test_go_requires_every_limitation_id_in_release_notes(tmp_path):
    manifest = copy.deepcopy(load_manifest(CURRENT_MANIFEST))
    manifest["candidate"] = "v9.9.9"
    manifest["release_notes"] = "release-notes.md"
    manifest["decision"]["outcome"] = "GO"
    for approval in manifest["decision"]["approvals"]:
        approval["status"] = "approved"
    for gate in manifest["gates"]:
        gate["status"] = "pass"
        gate["evidence"] = ["https://github.com/healplus/healplus/actions"]
    manifest["rollback"]["procedure"] = "rollback.md"

    (tmp_path / "rollback.md").write_text("# Rollback\n", encoding="utf-8")
    limitation_ids = [item["id"] for item in manifest["limitations"]]
    (tmp_path / "release-notes.md").write_text(
        "# Limitações\n" + "\n".join(limitation_ids),
        encoding="utf-8",
    )

    assert validate_manifest(manifest, project_root=tmp_path, require_go=True) == []

    (tmp_path / "release-notes.md").write_text("# Limitações\n#53\n", encoding="utf-8")
    errors = validate_manifest(manifest, project_root=tmp_path, require_go=True)

    assert any("release notes must reference every limitation id" in error for error in errors)
