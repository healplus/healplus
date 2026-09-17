import io
import time

import pytest
from PIL import Image

from src.dashboard.clinical_dashboard import ClinicalDashboard
from src.data.database import Database, PatientRecord


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "0")
    db = Database(str(tmp_path / "test.db"))
    db.save_patient(PatientRecord(id="p001", name="Paciente Teste"))
    app = ClinicalDashboard(database=db).create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _png_bytes(color: tuple[int, int, int] = (180, 20, 20)) -> bytes:
    buffer = io.BytesIO()
    image = Image.new("RGB", (32, 32), color=color)
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _create_completed_job(client, *, evaluation_date: str, area: float = 9.0) -> tuple[dict, str]:
    evaluation_response = client.post(
        "/api/v1/evaluations",
        json={
            "patient_id": "p001",
            "evaluation_date": evaluation_date,
            "wound_area_cm2": area,
            "depth_mm": 4.0,
            "pain_score": 5,
        },
    )
    assert evaluation_response.status_code == 201
    evaluation = evaluation_response.get_json()
    analyze_response = client.post(
        f"/api/v1/evaluations/{evaluation['id']}/analyze",
        json={"forceFallback": True},
    )
    assert analyze_response.status_code == 202
    job_id = analyze_response.get_json()["jobId"]
    for _ in range(20):
        job_response = client.get(f"/api/v1/analysis-jobs/{job_id}")
        if job_response.get_json()["job"]["status"] == "completed":
            return evaluation, job_id
        time.sleep(0.2)
    pytest.fail("Job de IA nao concluiu dentro do tempo esperado.")


def test_health_contract(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["status"] == "ok"
    assert "metrics" in payload


def test_evaluation_image_analyze_job_contract(client):
    create_resp = client.post(
        "/api/v1/evaluations",
        json={
            "patient_id": "p001",
            "evaluation_date": "2026-03-19",
            "wound_type": "venous_ulcer",
            "wound_location": "perna direita",
            "clinical_description": "teste",
            "wound_area_cm2": 10.0,
            "depth_mm": 3.0,
            "pain_score": 5,
            "tissue_composition": {"granulation": 50, "slough": 40, "necrosis": 10},
        },
    )
    assert create_resp.status_code == 201
    evaluation = create_resp.get_json()
    evaluation_id = evaluation["id"]

    upload_resp = client.post(
        f"/api/v1/evaluations/{evaluation_id}/images",
        data={"imageRole": "frontal", "image": (io.BytesIO(_png_bytes()), "wound.png")},
        content_type="multipart/form-data",
    )
    assert upload_resp.status_code == 201

    analyze_resp = client.post(f"/api/v1/evaluations/{evaluation_id}/analyze", json={})
    assert analyze_resp.status_code == 202
    job_id = analyze_resp.get_json()["jobId"]

    for _ in range(15):
        status_resp = client.get(f"/api/v1/analysis-jobs/{job_id}")
        assert status_resp.status_code == 200
        payload = status_resp.get_json()
        if payload["job"]["status"] == "completed":
            assert payload["result"] is not None
            assert payload["result"]["contract_version"] == "2026-04-07"
            assert payload["result"]["model_version"] == "fallback-clinical-v1"
            assert payload["result"]["evaluation_id"] == evaluation_id
            assert payload["result"]["case_id"] == evaluation["case_id"]
            assert payload["result"]["inference"]["confidence"] == payload["result"]["confidence"]
            assert payload["result"]["interpretation"]["risk_level"] in {"baixo", "moderado", "alto", "critico"}
            assert payload["result"]["review"] == {"status": "pending"}
            break
        time.sleep(0.2)
    else:
        pytest.fail("Job de IA nao concluiu dentro do tempo esperado.")

    pending_lesions = client.get("/api/v1/patients/p001/lesions").get_json()
    assert pending_lesions[0]["active_care_plan"] is None

    review_resp = client.post(
        f"/api/v1/analysis-jobs/{job_id}/review",
        json={
            "decision": "approved",
            "reason_code": "clinically_confirmed",
            "notes": "Resultado conferido com a avaliação sintética.",
        },
    )
    assert review_resp.status_code == 200
    assert review_resp.get_json()["result"]["review"]["status"] == "approved"

    audit_response = client.get(f"/api/v1/lesions/{evaluation['case_id']}/audit")
    assert audit_response.status_code == 200
    audit_actions = {event["action"] for event in audit_response.get_json()}
    assert {
        "evaluation_created",
        "clinical_image_uploaded",
        "analysis_requested",
        "analysis_completed",
    } <= audit_actions


def test_lesion_timeline_closes_main_flow(client):
    create_resp = client.post(
        "/api/v1/evaluations",
        json={
            "patient_id": "p001",
            "evaluation_date": "2026-03-20",
            "wound_type": "venous_ulcer",
            "wound_location": "perna esquerda",
            "clinical_description": "ferida cronica",
            "wound_area_cm2": 11.0,
            "depth_mm": 4.0,
            "pain_score": 6,
            "tissue_composition": {"granulation": 50, "slough": 35, "necrosis": 15},
        },
    )
    assert create_resp.status_code == 201
    evaluation = create_resp.get_json()

    upload_resp = client.post(
        f"/api/v1/evaluations/{evaluation['id']}/images",
        data={"imageRole": "clinical", "image": (io.BytesIO(_png_bytes()), "wound.png")},
        content_type="multipart/form-data",
    )
    assert upload_resp.status_code == 201
    image = upload_resp.get_json()
    assert image["version"] == 1
    assert image["review_status"] == "nao_revisada"

    analyze_resp = client.post(f"/api/v1/evaluations/{evaluation['id']}/analyze", json={})
    assert analyze_resp.status_code == 202
    job_id = analyze_resp.get_json()["jobId"]

    for _ in range(15):
        status_resp = client.get(f"/api/v1/analysis-jobs/{job_id}")
        payload = status_resp.get_json()
        if payload["job"]["status"] == "completed":
            break
        time.sleep(0.2)
    else:
        pytest.fail("Job de IA nao concluiu dentro do tempo esperado.")

    review_resp = client.post(
        f"/api/v1/analysis-jobs/{job_id}/review",
        json={
            "decision": "approved",
            "reason_code": "clinically_confirmed",
            "notes": "Resultado conferido com a avaliação sintética.",
        },
    )
    assert review_resp.status_code == 200

    lesions_resp = client.get("/api/v1/patients/p001/lesions")
    assert lesions_resp.status_code == 200
    lesions = lesions_resp.get_json()
    assert len(lesions) == 1
    assert lesions[0]["active_care_plan"] is not None
    assert lesions[0]["latest_inference_result"] is not None

    timeline_resp = client.get(f"/api/v1/lesions/{evaluation['case_id']}/timeline")
    assert timeline_resp.status_code == 200
    timeline = timeline_resp.get_json()
    assert timeline["lesion"]["id"] == evaluation["case_id"]
    assert timeline["summary"]["active_care_plan_id"] is not None
    assert timeline["summary"]["next_follow_up"] is not None
    assert timeline["summary"]["latest_risk_level"] in {"baixo", "moderado", "alto", "critico"}
    event_types = [event["type"] for event in timeline["events"]]
    assert "assessment" in event_types
    assert "clinical_image" in event_types
    assert "inference_result" in event_types
    assert "care_plan" in event_types
    assert "follow_up" in event_types
    assert "alert" in event_types


def test_professional_review_supports_correction_and_rejection(client):
    corrected_evaluation, corrected_job = _create_completed_job(
        client,
        evaluation_date="2026-03-21",
    )
    corrected_response = client.post(
        f"/api/v1/analysis-jobs/{corrected_job}/review",
        json={
            "decision": "corrected",
            "reason_code": "corrected_measurement",
            "notes": "Medida corrigida após conferência profissional.",
            "corrections": {
                "wound_area_cm2": 5.5,
                "risk_level": "moderado",
                "summary": "Síntese corrigida após revisão profissional.",
            },
        },
    )
    assert corrected_response.status_code == 200
    corrected = corrected_response.get_json()
    assert corrected["result"]["review"]["status"] == "corrected"
    assert corrected["result"]["review"]["changed_fields"] == [
        "risk_level",
        "summary",
        "wound_area_cm2",
    ]
    assert corrected["result"]["inference"]["wound_area_cm2"] == 5.5
    assert corrected["care_plan"]["created_by"]
    assert corrected["care_plan"]["metadata"]["review_status"] == "corrected"

    rejected_evaluation, rejected_job = _create_completed_job(
        client,
        evaluation_date="2026-03-22",
    )
    rejected_response = client.post(
        f"/api/v1/analysis-jobs/{rejected_job}/review",
        json={
            "decision": "rejected",
            "reason_code": "insufficient_evidence",
            "notes": "Imagem sintética insuficiente para uso clínico.",
        },
    )
    assert rejected_response.status_code == 200
    rejected = rejected_response.get_json()
    assert rejected["result"]["review"]["status"] == "rejected"
    assert rejected["care_plan"] is None
    assert rejected["follow_up"] is None
    assert rejected["alerts"] == []

    repeated_response = client.post(
        f"/api/v1/analysis-jobs/{rejected_job}/review",
        json={
            "decision": "approved",
            "reason_code": "clinically_confirmed",
            "notes": "Tentativa repetida deve ser bloqueada.",
        },
    )
    assert repeated_response.status_code == 409

    rejected_timeline = client.get(
        f"/api/v1/lesions/{rejected_evaluation['case_id']}/timeline"
    ).get_json()
    inference_event = next(
        event for event in rejected_timeline["events"] if event["type"] == "inference_result"
    )
    assert inference_event["status"] == "rejected"
    assert rejected_timeline["care_plans"] == []

    corrected_audit = client.get(
        f"/api/v1/lesions/{corrected_evaluation['case_id']}/audit"
    ).get_json()
    assert "inference_result_reviewed" in {event["action"] for event in corrected_audit}


def test_comparison_deltas_contract(client):
    base = client.post(
        "/api/v1/evaluations",
        json={
            "patient_id": "p001",
            "evaluation_date": "2026-03-01",
            "wound_area_cm2": 12.0,
            "depth_mm": 4.0,
            "pain_score": 7,
            "push_score": 12,
            "bwat_score": 35,
            "tissue_composition": {"granulation": 40, "slough": 45, "necrosis": 15},
        },
    ).get_json()

    follow = client.post(
        "/api/v1/evaluations",
        json={
            "patient_id": "p001",
            "case_id": base["case_id"],
            "evaluation_date": "2026-03-10",
            "wound_area_cm2": 9.0,
            "depth_mm": 3.0,
            "pain_score": 4,
            "push_score": 8,
            "bwat_score": 28,
            "tissue_composition": {"granulation": 60, "slough": 30, "necrosis": 10},
        },
    ).get_json()

    resp = client.get(f"/api/v1/comparisons?left={base['id']}&right={follow['id']}")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["deltas"]["area_cm2"] == -3.0
    assert payload["deltas"]["depth_mm"] == -1.0
    assert payload["deltas"]["pain_score"] == -3.0
    assert payload["deltas"]["tissue"]["granulation"] == 20.0
