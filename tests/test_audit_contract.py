from __future__ import annotations

import json
import math
import sqlite3

import pytest

from packages.clinical_domain import Database
from packages.shared.audit import AuditContractError, build_audit_event


def _event_payload() -> dict[str, object]:
    return {
        "actor_type": "human",
        "actor_id": "synthetic-user-a",
        "actor_role": "nurse",
        "action": "evaluation_reviewed",
        "target_type": "evaluation",
        "target_id": "synthetic-evaluation-1",
        "patient_id": "synthetic-patient-1",
        "case_id": "synthetic-case-1",
        "request_id": "synthetic-request-1",
        "outcome": "succeeded",
        "metadata": {
            "source": "clinical_api",
            "review_required": True,
        },
    }


def test_audit_contract_accepts_only_minimal_allowlisted_metadata():
    event = build_audit_event(_event_payload())

    assert event["contract_version"] == "1.0"
    assert event["metadata"] == {
        "source": "clinical_api",
        "review_required": True,
    }
    assert "before_json" not in event
    assert "after_json" not in event


@pytest.mark.parametrize(
    "metadata",
    [
        {"notes": "conteúdo clínico"},
        {"prompt": "instrução interna"},
        {"api_key": "secret"},
        {"patient_name": "Paciente Sintético"},
        {"image_base64": "bytes"},
    ],
)
def test_audit_contract_rejects_sensitive_or_unknown_metadata(metadata):
    payload = {**_event_payload(), "metadata": metadata}

    with pytest.raises(AuditContractError):
        build_audit_event(payload)


@pytest.mark.parametrize(
    "changes",
    [
        {"created_at": "2026-07-27T10:00:00"},
        {"created_at": "not-a-date"},
        {"metadata": {"attempts": math.nan}},
        {"patient_id": "x" * 181},
    ],
)
def test_audit_contract_rejects_invalid_dates_non_finite_values_and_oversized_ids(changes):
    with pytest.raises(AuditContractError):
        build_audit_event({**_event_payload(), **changes})


def test_database_audit_events_are_append_only_and_do_not_store_snapshots(tmp_path):
    database = Database(str(tmp_path / "audit.db"))
    created = database.create_audit_event(
        {
            **_event_payload(),
            "before_json": {"notes": "não persistir"},
            "after_json": {"notes": "não persistir"},
            "metadata": {
                "source": "clinical_api",
                "notes": "não persistir",
                "run_id": "synthetic-run-1",
            },
        }
    )

    assert created is not None
    events = database.list_case_audit_events("synthetic-case-1")
    assert len(events) == 1
    assert events[0]["before_json"] is None
    assert events[0]["after_json"] is None
    assert events[0]["metadata"] == {
        "source": "clinical_api",
        "run_id": "synthetic-run-1",
    }

    with database._get_connection() as connection:
        raw = connection.execute(
            "SELECT metadata FROM audit_events_v1 WHERE id = ?",
            (created["id"],),
        ).fetchone()
        assert json.loads(raw["metadata"]) == events[0]["metadata"]
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE audit_events_v1 SET outcome = 'failed' WHERE id = ?",
                (created["id"],),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "DELETE FROM audit_events_v1 WHERE id = ?",
                (created["id"],),
            )
