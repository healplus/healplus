"""Synthetic-only intake, authorization, custody and multi-process queue regressions."""

import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json

from fastapi.testclient import TestClient
import numpy as np
from PIL import Image
import pytest

from apps.quality_api.main import create_fastapi_app
from src.analysis_intake.fhir import validate_resource
from src.analysis_intake.repository import IntakeRepository
from src.analysis_intake.worker import IntakeWorker
from src.image_quality.repository import QualityRepository
from src.image_quality.service import ImageQualityService
from src.image_quality.storage import LocalStorageBackend


def jpeg(*, defective=False):
    y, x = np.indices((480, 640))
    pattern = (110 + 35 * np.sin(x / 1.5) + 30 * np.cos(y / 2)).astype(np.uint8)
    rgb = np.stack((pattern + 25, pattern, pattern - 20), axis=2)
    if defective:
        rgb[:] = 0
    output = io.BytesIO()
    Image.fromarray(rgb).save(output, format="JPEG", quality=95)
    return output.getvalue()


def media(identifier="photo-1", *, defective=False):
    return {
        "resourceType": "Media",
        "id": identifier,
        "status": "completed",
        "subject": {"reference": "Patient/patient-one"},
        "createdDateTime": "2026-09-21T10:15:00Z",
        "content": {"contentType": "image/jpeg", "data": base64.b64encode(jpeg(defective=defective)).decode("ascii")},
    }


def bundle(*images):
    return {"resourceType": "Bundle", "type": "collection", "entry": [{"resource": m} for m in images]}


HEADERS = {
    "Authorization": "Bearer owner",
    "Content-Type": "application/fhir+json",
    "X-Patient-Consent": "true",
    "Idempotency-Key": "synthetic-request-1",
}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "1")
    repo = IntakeRepository(tmp_path / "intake.db")

    def auth(token):
        if token == "invalid":
            raise ValueError("private token")
        return {"uid": token, "role": "researcher" if token == "researcher" else "doctor"}

    def patient(user, pid):
        if user["uid"] not in {"owner", "second"} or pid != "patient-one":
            return None
        return {"id": pid, "name": "Synthetic patient", "birth_date": "1980-01-02", "notes": "Must never be copied"}

    service = ImageQualityService(LocalStorageBackend(tmp_path / "legacy"), QualityRepository(tmp_path / "legacy.db"))
    app = create_fastapi_app(service, intake_repository=repo, auth_verifier=auth, patient_resolver=patient)
    return TestClient(app), repo, app


def post(client, payload=None, **headers):
    return client.post(
        "/api/v1/analyses", json=payload if payload is not None else media(), headers={**HEADERS, **headers}
    )


def test_batch_persistence_completion_and_private_retrieval(setup):
    client, repo, _ = setup
    response = post(client, bundle(media(), media("photo-2")))
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "QUEUED"
    assert body["task"]["status"] == "ready"
    validate_resource(body["task"])
    assert len(repo.images(body["analysisId"])) == 2
    url = body["statusUrl"]
    stored = client.get(url + "/payload", headers=HEADERS).json()
    validate_resource(stored)
    patient = stored["entry"][0]["resource"]
    assert patient["name"] == [{"text": "Synthetic patient"}]
    assert patient["birthDate"] == "1980-01-02"
    assert "notes" not in json.dumps(stored)
    assert "data" not in stored["entry"][1]["resource"]["content"]
    original = client.get(url + "/images/photo-1", headers=HEADERS)
    assert original.content == jpeg()
    assert original.headers["cache-control"] == "no-store"
    assert client.get(url + "/result", headers=HEADERS).status_code == 202

    def analyze(image, record):
        assert image["sha256"] == hashlib.sha256(jpeg()).hexdigest()
        assert client.get(url, headers=HEADERS).json()["status"] == "PROCESSING"
        return {"measured": True}

    assert IntakeWorker(IntakeRepository(repo.path), analyzer=analyze).run_once()
    status = client.get(url, headers=HEADERS).json()
    assert [event["status"] for event in status["history"]] == ["ACCEPTED", "QUEUED", "PROCESSING", "COMPLETED"]
    validate_resource(status["task"])
    result = client.get(url + "/result", headers=HEADERS)
    assert result.status_code == 200
    assert len(result.json()["images"]) == 2
    assert result.json()["clinicianReviewRequired"] is True
    assert not IntakeWorker(repo, analyzer=analyze).run_once()


@pytest.mark.parametrize("token,expected", [("invalid", 401), ("researcher", 403), ("unassigned", 404)])
def test_denied_users_never_enqueue(setup, token, expected):
    client, repo, _ = setup
    response = post(client, Authorization=f"Bearer {token}")
    assert response.status_code == expected
    assert "private token" not in response.text
    assert repo.claim() is None


def test_consent_missing_auth_and_disabled_auth(setup, monkeypatch):
    client, repo, _ = setup
    for consent in ("", "false", "1", "TRUE"):
        assert post(client, **{"X-Patient-Consent": consent}).status_code == 403
    assert post(client, Authorization="").status_code == 401
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "0")
    assert post(client).status_code == 503
    assert repo.claim() is None


def test_ownership_and_revoked_patient_scope(setup):
    client, _, app = setup
    body = post(client).json()
    for suffix in ("", "/payload", "/result", "/images/photo-1"):
        assert (
            client.get(body["statusUrl"] + suffix, headers={**HEADERS, "Authorization": "Bearer second"}).status_code
            == 404
        )
    app.state.intake_patient_resolver = lambda user, pid: None
    assert client.get(body["statusUrl"], headers=HEADERS).status_code == 404


def test_patient_completion_does_not_trust_supplied_demographics(setup):
    client, _, _ = setup
    image = media()
    del image["subject"]
    payload = bundle({"resourceType": "Patient", "id": "patient-one", "name": [{"text": "Untrusted name"}]}, image)
    body = post(client, payload).json()
    resource = client.get(body["payloadUrl"], headers=HEADERS).json()
    assert resource["entry"][0]["resource"]["name"][0]["text"] == "Synthetic patient"


def test_task_with_contained_media(setup):
    client, _, _ = setup
    image = media()
    del image["subject"]
    task = {
        "resourceType": "Task",
        "status": "requested",
        "intent": "order",
        "for": {"reference": "Patient/patient-one"},
        "contained": [image],
        "input": [{"type": {"text": "Image"}, "valueReference": {"reference": "#photo-1"}}],
    }
    response = post(client, task)
    assert response.status_code == 202, response.text


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.update(resourceType="Observation"),
        lambda p: p.update(resourceType=["Media"]),
        lambda p: p.update(status="not-a-fhir-status"),
        lambda p: p.update(unrecognized="field"),
        lambda p: p.update(createdDateTime="not-a-date"),
        lambda p: p.update(createdDateTime="2026-09-21T10:15:00"),
        lambda p: p.update(width=123),
        lambda p: p.pop("createdDateTime"),
        lambda p: p.pop("subject"),
        lambda p: p.update(subject={"reference": "https://attacker.invalid/Patient/patient-one"}),
        lambda p: p["content"].update(data="bad base64"),
        lambda p: p["content"].update(size=123),
        lambda p: p["content"].update(hash="abcd"),
        lambda p: p["content"].update(url="http://127.0.0.1/private"),
        lambda p: p["content"].update(contentType="image/png"),
        lambda p: p.update(modifierExtension=[{"url": "https://unknown.invalid", "valueBoolean": True}]),
    ],
)
def test_invalid_payloads_have_no_side_effects(setup, mutation):
    client, repo, _ = setup
    payload = media()
    mutation(payload)
    response = post(client, payload)
    assert response.status_code in {400, 415, 422}, response.text
    assert response.json()["resourceType"] == "OperationOutcome"
    assert repo.claim() is None


def test_empty_duplicate_and_mixed_batches(setup):
    client, repo, _ = setup
    other = media("photo-2")
    other["subject"]["reference"] = "Patient/another"
    for payload in (
        bundle(),
        bundle(media(), media()),
        bundle(media(), other),
        bundle(*[media(f"p-{i}") for i in range(9)]),
    ):
        assert post(client, payload).status_code == 422
    assert repo.claim() is None


def test_quality_rejection_is_atomic_and_retains_no_images(setup):
    client, repo, _ = setup
    response = post(client, bundle(media(), media("blurry", defective=True)))
    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "REJECTED"
    assert repo.images(body["analysisId"]) == []
    assert repo.claim() is None
    assert client.get(body["resultUrl"], headers=HEADERS).status_code == 409
    stored = client.get(body["payloadUrl"], headers=HEADERS).json()
    assert all(
        "data" not in e["resource"].get("content", {}) and "url" not in e["resource"].get("content", {})
        for e in stored["entry"]
    )


def test_idempotency_and_parallel_claims(setup):
    client, repo, _ = setup
    first = post(client).json()
    assert post(client).json()["analysisId"] == first["analysisId"]
    assert post(client, media("different")).status_code == 409
    assert post(client, Authorization="Bearer second").status_code == 202
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(lambda _: IntakeRepository(repo.path).claim(), range(4)))
    assert len([r for r in claims if r]) == 2
    assert len({r["id"] for r in claims if r}) == 2


def test_database_failure_rolls_back_everything(setup):
    client, repo, _ = setup
    with repo.connection() as db:
        db.execute(
            "CREATE TRIGGER reject_image BEFORE INSERT ON intake_images BEGIN SELECT RAISE(ABORT, 'private storage error'); END"
        )
    response = post(client)
    assert response.status_code == 503
    assert "private storage error" not in response.text
    with repo.connection() as db:
        for table in ("intake_analyses", "intake_images", "intake_events"):
            assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


def test_worker_restart_and_fencing(setup):
    client, repo, _ = setup
    body = post(client).json()
    old = repo.claim()
    with repo.connection() as db:
        db.execute("UPDATE intake_analyses SET lease_until=0 WHERE id=?", (body["analysisId"],))
    current = IntakeRepository(repo.path).claim()
    assert current["id"] == old["id"] and current["lease_token"] != old["lease_token"]
    assert not repo.finish(old, result={"stale": True})
    assert repo.finish(current, result={"fresh": True})
    assert client.get(body["resultUrl"], headers=HEADERS).json() == {"fresh": True}


def test_worker_retry_exhaustion_and_error_redaction(setup):
    client, repo, _ = setup
    body = post(client).json()

    def failing(image, record):
        raise RuntimeError("secret patient data")

    worker = IntakeWorker(repo, analyzer=failing, max_attempts=2)
    assert worker.run_once()
    assert client.get(body["statusUrl"], headers=HEADERS).json()["status"] == "QUEUED"
    with repo.connection() as db:
        db.execute("UPDATE intake_analyses SET available_at=0")
    assert worker.run_once()
    response = client.get(body["statusUrl"], headers=HEADERS)
    assert response.json()["status"] == "FAILED"
    assert "secret patient data" not in response.text
    assert not worker.run_once()


def test_corrupt_custody_does_not_reach_analyzer(setup):
    client, repo, _ = setup
    body = post(client).json()
    with repo.connection() as db:
        db.execute("UPDATE intake_images SET content=?", (b"corrupted",))
    called = []
    IntakeWorker(repo, analyzer=lambda *args: called.append(args), max_attempts=1).run_once()
    assert not called
    assert client.get(body["statusUrl"], headers=HEADERS).json()["status"] == "FAILED"


def test_malformed_json_body_limit_and_busy_slot(setup, monkeypatch):
    client, repo, app = setup
    response = client.post(
        "/api/v1/analyses", content='{"resourceType":"Media","resourceType":"Task"}', headers=HEADERS
    )
    assert response.status_code == 400
    assert post(client, **{"Content-Type": "application/json"}).status_code == 415
    assert post(client, **{"Idempotency-Key": "short"}).status_code == 400
    monkeypatch.setattr("apps.quality_api.intake.MAX_BATCH_BYTES", 50)
    assert post(client).status_code == 413
    app.state.intake_slots.acquire()
    app.state.intake_slots.acquire()
    assert post(client).status_code == 429
    app.state.intake_slots.release()
    app.state.intake_slots.release()
    assert repo.claim() is None


def test_default_supabase_resolver_uses_callers_token_and_minimal_fields(setup, monkeypatch):
    client, _, app = setup
    app.state.intake_patient_resolver = None
    calls = []

    class Client:
        def __init__(self, token):
            assert token == "owner"

        def select(self, table, **params):
            calls.append((table, params))
            return [{"id": "patient-one", "name": "Synthetic", "birth_date": "1980-01-02"}]

    monkeypatch.setattr("apps.quality_api.intake.SupabaseClient", Client)
    assert post(client).status_code == 202
    assert calls == [
        (
            "patients",
            {
                "select": "id,name,birth_date",
                "id": "eq.patient-one",
                "user_id": "eq.owner",
                "archived": "eq.false",
                "limit": "1",
            },
        )
    ]


def test_canonical_worker_in_separate_process(setup):
    import os
    from pathlib import Path
    import subprocess
    import sys

    client, repo, _ = setup
    body = post(client).json()
    process = subprocess.run(
        [sys.executable, "-m", "src.analysis_intake.worker", "--once"],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "HEAL_INTAKE_DB_PATH": str(repo.path)},
        capture_output=True,
        timeout=120,
    )
    assert process.returncode == 0, process.stderr.decode(errors="replace")
    state = client.get(body["statusUrl"], headers=HEADERS).json()
    assert state["status"] == "COMPLETED", state
    result = client.get(body["resultUrl"], headers=HEADERS).json()["images"][0]["result"]
    assert result["resource_type"] == "wound_analysis"
    assert result["safety"]["decision_support_only"] is True
    assert result["metadata"]["original_sha256"] == hashlib.sha256(jpeg()).hexdigest()


def test_expired_final_attempt_becomes_failed(setup):
    client, repo, _ = setup
    body = post(client).json()
    repo.claim(max_attempts=1)
    with repo.connection() as db:
        db.execute("UPDATE intake_analyses SET lease_until=0")
    assert repo.claim(max_attempts=1) is None
    assert client.get(body["statusUrl"], headers=HEADERS).json()["status"] == "FAILED"


def test_parallel_retries_store_one_batch(setup):
    client, repo, _ = setup
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: post(client), range(2)))
    assert all(r.status_code == 202 for r in results)
    assert len({r.json()["analysisId"] for r in results}) == 1
    assert len(repo.images(results[0].json()["analysisId"])) == 1


def test_read_requests_require_authentication(setup):
    client, _, _ = setup
    body = post(client).json()
    for suffix in ("", "/result", "/payload", "/images/photo-1"):
        response = client.get(body["statusUrl"] + suffix)
        assert response.status_code == 401
        assert response.headers["cache-control"] == "no-store"


def test_heartbeat_keeps_long_running_analysis_reserved(setup):
    import threading
    import time

    client, repo, _ = setup
    body = post(client).json()
    started, release = threading.Event(), threading.Event()

    def slow_analysis(image, record):
        started.set()
        assert release.wait(15)
        return {"finished": True}

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(IntakeWorker(repo, analyzer=slow_analysis, lease_seconds=3).run_once)
        try:
            assert started.wait(10)
            time.sleep(4)
            assert IntakeRepository(repo.path).claim() is None
        finally:
            release.set()
        assert future.result(timeout=10)
    assert client.get(body["statusUrl"], headers=HEADERS).json()["status"] == "COMPLETED"
