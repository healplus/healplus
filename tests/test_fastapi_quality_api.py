# -*- coding: utf-8 -*-
"""Comprehensive tests for the FastAPI Image Quality and FHIR R4 service."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from apps.quality_api.main import create_fastapi_app
from src.image_quality.repository import QualityRepository
from src.image_quality.service import ImageQualityService
from src.image_quality.storage import LocalStorageBackend


def create_synthetic_photograph(width: int = 640, height: int = 480) -> np.ndarray:
    """Generate a reproducible, synthetic clinical-like texture pattern."""
    y, x = np.indices((height, width))
    pattern = (110 + 35 * np.sin(x / 1.5) + 30 * np.cos(y / 2)).astype(np.uint8)
    return np.stack((pattern + 25, pattern, pattern - 20), axis=2)


def to_jpeg_bytes(rgb: np.ndarray, quality: int = 95) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(rgb).save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()


def to_base64_jpeg(rgb: np.ndarray) -> str:
    return base64.b64encode(to_jpeg_bytes(rgb)).decode("ascii")


@pytest.fixture
def quality_app(tmp_path: Path):
    storage_dir = tmp_path / "storage"
    db_path = tmp_path / "quality_test.db"
    storage = LocalStorageBackend(base_dir=storage_dir)
    repository = QualityRepository(db_path=db_path)
    service = ImageQualityService(storage=storage, repository=repository)
    app = create_fastapi_app(service=service)
    return app, service, storage_dir


@pytest.fixture
def client(quality_app):
    app, _, _ = quality_app
    return TestClient(app)


def test_health_check_endpoint(client):
    response = client.get("/api/v1/quality/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "healplus-image-quality-fastapi"
    assert "version" in data
    assert "opencv" in data["engine"]
    assert data["capabilities"]["opencv_sharpness"] is True
    assert data["capabilities"]["fhir_r4_media"] is True


def test_assess_sharp_image_approved_multipart(client, quality_app):
    _, service, storage_dir = quality_app
    sharp_rgb = create_synthetic_photograph()
    jpeg_bytes = to_jpeg_bytes(sharp_rgb)

    response = client.post(
        "/api/v1/quality/assess",
        files={"file": ("wound_sharp.jpg", jpeg_bytes, "image/jpeg")},
        data={"patient_id": "patient-456", "encounter_id": "encounter-789"},
    )
    assert response.status_code == 200
    result = response.json()

    assert result["decision"] == "aprovada"
    assert result["status"] == "accepted"
    assert result["patient_id"] == "patient-456"
    assert result["encounter_id"] == "encounter-789"
    assert len(result["findings"]) == 0
    assert result["actionable_advice"] is None

    # Verify metrics
    metrics = result["metrics"]
    assert metrics["width"] == 640
    assert metrics["height"] == 480
    assert metrics["sharpness"] > 10.0

    # Verify FHIR Bundle
    bundle = result["fhir_bundle"]
    assert bundle["resourceType"] == "Bundle"
    assert len(bundle["entry"]) == 2

    media_res = bundle["entry"][0]["resource"]
    assert media_res["resourceType"] == "Media"
    assert media_res["subject"]["reference"] == "Patient/patient-456"
    assert media_res["encounter"]["reference"] == "Encounter/encounter-789"
    assert media_res["content"]["contentType"] == "image/jpeg"

    obs_res = bundle["entry"][1]["resource"]
    assert obs_res["resourceType"] == "Observation"
    assert obs_res["status"] == "final"
    assert obs_res["interpretation"][0]["coding"][0]["code"] == "N"
    assert obs_res["focus"][0]["reference"] == f"Media/{media_res['id']}"

    # Verify FHIR validation
    validation = result["fhir_validation"]
    assert validation["validated"] is True
    assert validation["valid"] is True
    assert validation["errors"] == []

    # Verify physical file storage
    stored_ref = result["stored_image"]
    assert stored_ref["sha256"] is not None
    stored_files = list(storage_dir.rglob("*.jpg"))
    assert len(stored_files) == 1
    assert stored_files[0].read_bytes() == jpeg_bytes


def test_assess_sharp_image_approved_json(client):
    sharp_rgb = create_synthetic_photograph()
    b64_str = to_base64_jpeg(sharp_rgb)

    response = client.post(
        "/api/v1/quality/assess",
        json={
            "image_base64": b64_str,
            "filename": "wound_direct.jpg",
            "content_type": "image/jpeg",
            "patient_id": "patient-json",
            "encounter_id": "encounter-json",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "aprovada"
    assert data["status"] == "accepted"
    assert data["patient_id"] == "patient-json"


def test_assess_blurry_image_rejected(client):
    sharp_rgb = create_synthetic_photograph()
    blurry_rgb = cv2.GaussianBlur(sharp_rgb, (31, 31), 8)
    jpeg_bytes = to_jpeg_bytes(blurry_rgb)

    response = client.post(
        "/api/v1/quality/assess",
        files={"file": ("wound_blurry.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert response.status_code == 200
    result = response.json()

    assert result["decision"] == "nova_captura_necessaria"
    assert result["status"] == "rejected"
    codes = [f["code"] for f in result["findings"]]
    assert "blur" in codes
    assert result["actionable_advice"] is not None
    assert "foco" in result["actionable_advice"].lower() or "estabilize" in result["actionable_advice"].lower()


@pytest.mark.parametrize(
    "generate_fn,expected_code",
    [
        (lambda: np.zeros((480, 640, 3), dtype=np.uint8), "underexposure"),
        (lambda: np.full((480, 640, 3), 255, dtype=np.uint8), "overexposure"),
        (lambda: create_synthetic_photograph(320, 240), "low-resolution"),
    ],
)
def test_assess_defective_images_rejected(client, generate_fn, expected_code):
    rgb = generate_fn()
    jpeg_bytes = to_jpeg_bytes(rgb)

    response = client.post(
        "/api/v1/quality/assess",
        files={"file": ("wound_defective.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["decision"] == "nova_captura_necessaria"
    assert result["status"] == "rejected"
    codes = [f["code"] for f in result["findings"]]
    assert expected_code in codes


def test_assess_glare_image_indeterminate(client):
    rgb = create_synthetic_photograph()
    rgb[:120, :160] = 255  # bright hot spot
    jpeg_bytes = to_jpeg_bytes(rgb)

    response = client.post(
        "/api/v1/quality/assess",
        files={"file": ("wound_glare.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "indeterminate"
    assert result["decision"] == "nova_captura_necessaria"
    codes = [f["code"] for f in result["findings"]]
    assert "possible-glare" in codes


def test_fhir_validate_image_endpoint(client):
    sharp_rgb = create_synthetic_photograph()
    b64 = to_base64_jpeg(sharp_rgb)

    payload = {
        "resourceType": "Parameters",
        "parameter": [
            {"name": "imageId", "valueString": "test-img-001"},
            {"name": "consent", "valueBoolean": True},
            {
                "name": "image",
                "valueAttachment": {
                    "contentType": "image/jpeg",
                    "data": b64,
                },
            },
        ],
    }

    response = client.post(
        "/api/v1/quality/fhir/$validate-image",
        json=payload,
        headers={"Accept": "application/fhir+json"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["resourceType"] == "Parameters"
    params = {p["name"]: p for p in data["parameter"]}
    assert params["status"]["valueCode"] == "accepted"


def test_fhir_metadata_endpoints(client):
    meta_resp = client.get("/api/v1/quality/fhir/metadata")
    assert meta_resp.status_code == 200
    meta_data = meta_resp.json()
    assert meta_data["resourceType"] == "CapabilityStatement"

    op_resp = client.get("/api/v1/quality/fhir/OperationDefinition/validate-image")
    assert op_resp.status_code == 200
    op_data = op_resp.json()
    assert op_data["resourceType"] == "OperationDefinition"
    assert op_data["code"] == "validate-image"


def test_history_queries(client):
    sharp_rgb = create_synthetic_photograph()
    jpeg_bytes = to_jpeg_bytes(sharp_rgb)

    # Post 2 evaluations for patient-history
    resp1 = client.post(
        "/api/v1/quality/assess",
        files={"file": ("w1.jpg", jpeg_bytes, "image/jpeg")},
        data={"patient_id": "patient-history", "encounter_id": "enc-1"},
    )
    assert resp1.status_code == 200
    eval1_id = resp1.json()["id"]

    resp2 = client.post(
        "/api/v1/quality/assess",
        files={"file": ("w2.jpg", jpeg_bytes, "image/jpeg")},
        data={"patient_id": "patient-history", "encounter_id": "enc-2"},
    )
    assert resp2.status_code == 200
    eval2_id = resp2.json()["id"]

    # Query single evaluation
    single_resp = client.get(f"/api/v1/quality/evaluations/{eval1_id}")
    assert single_resp.status_code == 200
    single_data = single_resp.json()
    assert single_data["id"] == eval1_id
    assert single_data["patient_id"] == "patient-history"
    assert single_data["encounter_id"] == "enc-1"

    # Query patient list
    list_resp = client.get("/api/v1/quality/patients/patient-history/evaluations")
    assert list_resp.status_code == 200
    patient_records = list_resp.json()
    assert len(patient_records) == 2
    ids = {r["id"] for r in patient_records}
    assert eval1_id in ids
    assert eval2_id in ids

    # Query non-existent
    missing_resp = client.get("/api/v1/quality/evaluations/non-existent-uuid")
    assert missing_resp.status_code == 404


def test_error_handling_invalid_bytes(client):
    response = client.post(
        "/api/v1/quality/assess",
        files={"file": ("corrupted.jpg", b"not-a-valid-image-stream", "image/jpeg")},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "image_input_error"


def test_error_handling_missing_payload(client):
    response = client.post("/api/v1/quality/assess")
    assert response.status_code == 400
