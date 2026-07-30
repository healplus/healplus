"""Negative authorization matrix for known clinical resource identifiers."""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest
from loguru import logger

from src.data.database import PatientRecord

USER_A_ID = "synthetic-user-a"
USER_A_TOKEN = "synthetic-user-a-token"
USER_B_ID = "synthetic-user-b"
PATIENT_A_ID = "patient-a"
SENSITIVE_MARKER = "SYNTHETIC_CLINICAL_PAYLOAD_MUST_NOT_ESCAPE"


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {USER_A_TOKEN}"}


def _user(uid: str) -> dict[str, str]:
    return {
        "uid": uid,
        "email": f"{uid}@example.test",
        "name": f"Synthetic {uid}",
        "role": "clinician",
    }


@pytest.fixture
def authorization_context(tmp_path, monkeypatch) -> dict[str, Any]:
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "negative-authorization.db"))
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "1")

    from apps.heal_plus.api.app import create_app

    app = create_app()
    app.config["TESTING"] = True

    def verify_token(token: str) -> dict[str, str]:
        if token == USER_A_TOKEN:
            return _user(USER_A_ID)
        raise ValueError("invalid synthetic token")

    app.config["REDISUS_AUTH_VERIFIER"] = verify_token
    database = app.extensions["redisus_db"]

    own_patient = PatientRecord(
        id=PATIENT_A_ID,
        name="Synthetic Patient A",
        metadata={"owner_uid": USER_A_ID},
    )
    assert database.save_patient(own_patient)

    patient = PatientRecord(
        id="patient-b",
        name="Synthetic Patient B",
        notes=SENSITIVE_MARKER,
        metadata={"owner_uid": USER_B_ID},
    )
    assert database.save_patient(patient)

    wound_case = database.create_wound_case(
        patient.id,
        {
            "title": "Synthetic wound",
            "wound_type": "synthetic",
            "location": "synthetic",
            "metadata": {"created_by": USER_B_ID},
        },
    )
    assert wound_case

    evaluation = database.create_wound_evaluation(
        {
            "patient_id": patient.id,
            "case_id": wound_case["id"],
            "evaluation_date": "2026-01-01",
            "clinical_description": SENSITIVE_MARKER,
            "metadata": {"created_by": USER_B_ID},
        },
    )
    assert evaluation

    image_path = tmp_path / "synthetic-image.png"
    image_path.write_bytes(b"synthetic image fixture")
    image = database.add_wound_image(
        evaluation["id"],
        {
            "image_path": str(image_path),
            "content_type": "image/png",
            "metadata": {
                "patient_id": patient.id,
                "case_id": wound_case["id"],
                "fixture": "synthetic",
            },
        },
    )
    assert image

    job = database.create_ai_run(evaluation["id"], use_fallback=True)
    assert job

    report = database.create_structured_report(
        {
            "patient_id": patient.id,
            "case_id": wound_case["id"],
            "evaluation_id": evaluation["id"],
            "report_type": "evolution",
            "report_json": {"fixture": "synthetic"},
            "generated_by": USER_B_ID,
        },
    )
    assert report

    wound_analysis_id = "wound-analysis-b"
    assert database.save_wound_analysis_result(
        analysis_id=wound_analysis_id,
        owner_uid=USER_B_ID,
        patient_id=patient.id,
        evaluation_id=evaluation["id"],
        request_hash="synthetic-request-hash",
        idempotency_key=None,
        payload={"status": "completed", "fixture": "synthetic"},
    )

    standalone_wound_analysis_id = "standalone-wound-analysis-b"
    assert database.save_wound_analysis_result(
        analysis_id=standalone_wound_analysis_id,
        owner_uid=USER_B_ID,
        patient_id=None,
        evaluation_id=None,
        request_hash="synthetic-standalone-request-hash",
        idempotency_key=None,
        payload={"status": "completed", "fixture": "synthetic standalone"},
    )

    return {
        "app": app,
        "patient": patient.id,
        "wound": wound_case["id"],
        "wound_analysis": wound_analysis_id,
        "standalone_wound_analysis": standalone_wound_analysis_id,
        "evaluation": evaluation["id"],
        "image": image["id"],
        "job": job["id"],
        "report": report["id"],
    }


def _request_probe(client, probe: str, identifier: str):
    headers = _headers()
    if probe == "patient-read":
        return client.get(f"/api/patients/{identifier}", headers=headers)
    if probe == "patient-write":
        return client.post(
            "/api/v1/evaluations",
            headers={**headers, "Content-Type": "application/json"},
            json={"patient_id": identifier, "evaluation_date": "2026-01-02"},
        )
    if probe == "wound-read":
        return client.get(f"/api/v1/lesions/{identifier}/timeline", headers=headers)
    if probe == "wound-write":
        return client.patch(
            f"/api/v1/lesions/{identifier}/claim",
            headers={**headers, "Content-Type": "application/json"},
            json={"notes": "synthetic authorization probe"},
        )
    if probe == "wound-analysis-read":
        return client.get(f"/api/v1/wound-analyses/{identifier}", headers=headers)
    if probe == "evaluation-create-with-case":
        return client.post(
            "/api/v1/evaluations",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "patient_id": PATIENT_A_ID,
                "case_id": identifier,
                "evaluation_date": "2026-01-02",
            },
        )
    if probe == "evaluation-list-with-case":
        return client.get(
            f"/api/v1/patients/{PATIENT_A_ID}/evaluations?caseId={identifier}",
            headers=headers,
        )
    if probe == "evaluation-read":
        return client.get(
            f"/api/v1/comparisons?left={identifier}&right={identifier}",
            headers=headers,
        )
    if probe == "evaluation-image-write":
        return client.post(f"/api/v1/evaluations/{identifier}/images", headers=headers)
    if probe == "evaluation-analysis-write":
        return client.post(
            f"/api/v1/evaluations/{identifier}/analyze",
            headers={**headers, "Content-Type": "application/json"},
            json={},
        )
    if probe == "image-read":
        return client.get(f"/api/v1/images/{identifier}/content", headers=headers)
    if probe == "job-read":
        return client.get(f"/api/v1/analysis-jobs/{identifier}", headers=headers)
    if probe == "report-read":
        return client.get(f"/api/v1/reports/{identifier}/download?format=json", headers=headers)
    if probe == "report-write":
        return client.post(
            "/api/v1/reports/generate",
            headers={**headers, "Content-Type": "application/json"},
            json={"patient_id": identifier, "report_type": "evolution"},
        )
    if probe == "report-generate-with-case":
        return client.post(
            "/api/v1/reports/generate",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "patient_id": PATIENT_A_ID,
                "case_id": identifier,
                "report_type": "evolution",
            },
        )
    raise AssertionError(f"unknown probe: {probe}")


def _normalized_denial(response, identifier: str) -> dict[str, Any]:
    payload = response.get_json()
    assert isinstance(payload, dict)
    normalized = dict(payload)
    normalized["request_id"] = "<request-id>"
    instance = normalized.get("instance")
    if isinstance(instance, str):
        normalized["instance"] = instance.replace(identifier, "<resource-id>")
    return normalized


@pytest.mark.security
@pytest.mark.parametrize(
    ("probe", "resource"),
    [
        ("patient-read", "patient"),
        ("patient-write", "patient"),
        ("wound-read", "wound"),
        ("wound-write", "wound"),
        ("wound-analysis-read", "wound_analysis"),
        ("wound-analysis-read", "standalone_wound_analysis"),
        ("evaluation-create-with-case", "wound"),
        ("evaluation-list-with-case", "wound"),
        ("evaluation-read", "evaluation"),
        ("evaluation-image-write", "evaluation"),
        ("evaluation-analysis-write", "evaluation"),
        ("image-read", "image"),
        ("job-read", "job"),
        ("report-read", "report"),
        ("report-write", "patient"),
        ("report-generate-with-case", "wound"),
    ],
)
def test_known_cross_user_id_is_indistinguishable_from_missing_id(
    authorization_context,
    probe: str,
    resource: str,
):
    app = authorization_context["app"]
    known_other_user_id = authorization_context[resource]
    missing_id = f"missing-{resource}"

    with app.test_client() as client:
        denied = _request_probe(client, probe, known_other_user_id)
        missing = _request_probe(client, probe, missing_id)

    assert denied.status_code == missing.status_code == 404
    assert denied.content_type == missing.content_type == "application/problem+json"

    assert _normalized_denial(denied, known_other_user_id) == _normalized_denial(missing, missing_id)
    assert SENSITIVE_MARKER not in denied.get_data(as_text=True)
    assert USER_B_ID not in denied.get_data(as_text=True)


@pytest.mark.security
@pytest.mark.parametrize(
    ("probe", "lookup_method"),
    [
        ("patient-read", "get_patient"),
        ("wound-read", "get_wound_case"),
        ("evaluation-read", "get_wound_evaluation"),
        ("image-read", "get_wound_image"),
        ("job-read", "get_ai_run"),
        ("report-read", "get_structured_report"),
        ("wound-analysis-read", "get_wound_analysis_result"),
    ],
)
def test_malformed_repository_records_fail_closed_without_internal_error(
    authorization_context,
    monkeypatch,
    probe: str,
    lookup_method: str,
):
    app = authorization_context["app"]
    database = app.extensions["redisus_db"]
    monkeypatch.setattr(
        database,
        lookup_method,
        lambda identifier: {"id": "malformed"} if identifier == "malformed" else None,
    )

    with app.test_client() as client:
        response = _request_probe(client, probe, "malformed")
        missing = _request_probe(client, probe, "missing-malformed")

    assert response.status_code == 404
    payload = response.get_json()
    assert payload["code"] == "not_found"
    assert payload["detail"] != "unexpected backend error"
    assert _normalized_denial(response, "malformed") == _normalized_denial(missing, "missing-malformed")


@pytest.mark.security
def test_repository_failure_is_not_masked_as_not_found(authorization_context, monkeypatch, caplog):
    app = authorization_context["app"]
    database = app.extensions["redisus_db"]
    loguru_messages: list[str] = []
    sink_id = logger.add(lambda message: loguru_messages.append(str(message)))

    class UnavailableConnection:
        def __enter__(self):
            raise sqlite3.OperationalError("synthetic repository unavailable")

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    monkeypatch.setattr(database, "_get_connection", lambda: UnavailableConnection())

    try:
        with app.test_client() as client:
            response = client.get("/api/patients/repository-probe", headers=_headers())
    finally:
        logger.remove(sink_id)

    assert response.status_code == 503
    payload = response.get_json()
    assert payload["code"] == "repository_unavailable"
    assert payload["detail"] == "clinical repository unavailable"
    assert "synthetic repository unavailable" not in response.get_data(as_text=True)
    assert "synthetic repository unavailable" not in caplog.text
    assert "synthetic repository unavailable" not in "".join(loguru_messages)


@pytest.mark.security
def test_missing_repository_extension_is_reported_as_unavailable(authorization_context):
    app = authorization_context["app"]
    app.extensions.pop("redisus_db")

    with app.test_client() as client:
        response = client.get("/api/v1/wound-analyses/repository-probe", headers=_headers())

    assert response.status_code == 503
    payload = response.get_json()
    assert payload["code"] == "repository_unavailable"
    assert payload["detail"] == "clinical repository unavailable"


@pytest.mark.security
def test_denied_clinical_payload_is_not_copied_to_logs_or_error_response(
    authorization_context,
    caplog,
):
    app = authorization_context["app"]
    loguru_messages: list[str] = []
    sink_id = logger.add(lambda message: loguru_messages.append(str(message)))

    try:
        with app.test_client() as client:
            response = client.post(
                "/api/v1/evaluations",
                headers={**_headers(), "Content-Type": "application/json"},
                json={
                    "patient_id": authorization_context["patient"],
                    "evaluation_date": "2026-01-02",
                    "clinical_description": SENSITIVE_MARKER,
                },
            )
    finally:
        logger.remove(sink_id)

    assert response.status_code == 404
    assert SENSITIVE_MARKER not in response.get_data(as_text=True)
    assert SENSITIVE_MARKER not in caplog.text
    assert SENSITIVE_MARKER not in "".join(loguru_messages)
