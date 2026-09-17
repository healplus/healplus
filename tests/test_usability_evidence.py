from __future__ import annotations

import copy
from pathlib import Path

from scripts.validate_usability_evidence import load_evidence, validate_evidence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CURRENT_EVIDENCE = (
    PROJECT_ROOT
    / "docs"
    / "product"
    / "usability"
    / "evidence"
    / "golden-path-pilot-rehearsal-2026-07-29.json"
)


def test_current_pilot_rehearsal_evidence_is_valid():
    evidence = load_evidence(CURRENT_EVIDENCE)

    assert validate_evidence(evidence) == []


def test_completed_moderated_study_requires_minimum_live_sessions():
    evidence = copy.deepcopy(load_evidence(CURRENT_EVIDENCE))
    evidence["status"] = "moderated-sessions-complete"

    errors = validate_evidence(evidence)

    assert "moderated-sessions-complete requires the minimum live session count" in errors


def test_real_patient_data_is_rejected():
    evidence = copy.deepcopy(load_evidence(CURRENT_EVIDENCE))
    evidence["data_policy"]["real_patient_data"] = True

    errors = validate_evidence(evidence)

    assert "data_policy.real_patient_data must be false" in errors


def test_p0_and_p1_findings_require_a_tracked_action():
    evidence = copy.deepcopy(load_evidence(CURRENT_EVIDENCE))
    evidence["findings"][0].pop("action")

    errors = validate_evidence(evidence)

    assert "findings[0].action is required for P0/P1" in errors


def test_findings_must_keep_usability_and_safety_separate():
    evidence = copy.deepcopy(load_evidence(CURRENT_EVIDENCE))
    for finding in evidence["findings"]:
        finding["category"] = "safety"

    errors = validate_evidence(evidence)

    assert "findings must separate usability and safety categories" in errors


def test_versioned_evidence_rejects_identity_fields():
    evidence = copy.deepcopy(load_evidence(CURRENT_EVIDENCE))
    evidence["participant_target"]["email"] = "person@example.invalid"

    errors = validate_evidence(evidence)

    assert any("is prohibited in versioned usability evidence" in error for error in errors)

