"""Synthetic-only regressions for image quality, privacy and the FHIR boundary."""

import base64
import copy
import io
import json
import uuid

import cv2
import numpy as np
import pytest
from PIL import Image

from src.image_quality.assessment import POLICY, assess_image
from src.image_quality.decoder import DecodedImage, ImageInputError, decode_attachment
from src.image_quality.fhir import parse_parameters

ENDPOINT = "/api/v1/fhir/$validate-image"
HEADERS = {"Authorization": "Bearer clinician", "Content-Type": "application/fhir+json"}


def photograph(width=640, height=480):
    y, x = np.indices((height, width))
    pattern = (110 + 35 * np.sin(x / 1.5) + 30 * np.cos(y / 2)).astype(np.uint8)
    return np.stack((pattern + 25, pattern, pattern - 20), axis=2)


def attachment(rgb=None, *, fmt="PNG", **save_options):
    buffer = io.BytesIO()
    image = Image.fromarray(rgb if rgb is not None else photograph())
    image.save(buffer, format=fmt, **save_options)
    return {
        "contentType": f"image/{'jpeg' if fmt == 'JPEG' else fmt.lower()}",
        "data": base64.b64encode(buffer.getvalue()).decode("ascii"),
    }


def payload(image=None):
    return {
        "resourceType": "Parameters",
        "parameter": [
            {"name": "imageId", "valueString": "synthetic-image-001"},
            {"name": "consent", "valueBoolean": True},
            {"name": "image", "valueAttachment": image if image is not None else attachment()},
        ],
    }


def value(response, name):
    item = next(p for p in response["parameter"] if p["name"] == name)
    return next(v for k, v in item.items() if k != "name")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("REDISUS_DB_PATH", str(tmp_path / "quality.db"))
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "1")
    monkeypatch.setenv("REDISUS_RATE_LIMIT_IMAGE_QUALITY", "10000")
    from apps.api.app import create_app

    app = create_app()
    app.config["TESTING"] = True

    def verifier(token):
        if token == "expired":
            raise ValueError("secret-token-must-not-leak")
        return {"uid": f"quality-test-{token}-{tmp_path.name}", "role": token}

    app.config["REDISUS_AUTH_VERIFIER"] = verifier
    return app.test_client()


def post(client, body=None, headers=None):
    return client.post(
        ENDPOINT,
        data=json.dumps(body if body is not None else payload()),
        headers=headers if headers is not None else HEADERS,
    )


def assert_outcome(response, status):
    assert response.status_code == status, response.get_data(as_text=True)
    assert response.mimetype == "application/fhir+json"
    assert response.json["resourceType"] == "OperationOutcome"
    assert response.headers["Cache-Control"] == "no-store"


def assess(rgb):
    return assess_image(DecodedImage(rgb, rgb.shape[1], rgb.shape[0], False))


def test_sharp_color_image_passes_and_blur_rejects():
    sharp = assess(photograph())
    blurred = assess(cv2.GaussianBlur(photograph(), (31, 31), 8))
    assert sharp.status == "accepted", sharp
    assert blurred.status == "rejected"
    assert "blur" in {f.code for f in blurred.findings}
    assert sharp.metrics["sharpness"] > blurred.metrics["sharpness"]


@pytest.mark.parametrize(
    "rgb,reason",
    [
        (np.zeros((480, 640, 3), dtype=np.uint8), "underexposure"),
        (np.full((480, 640, 3), 255, dtype=np.uint8), "overexposure"),
        (np.full((480, 640, 3), 120, dtype=np.uint8), "low-contrast"),
        (photograph(320, 240), "low-resolution"),
    ],
)
def test_defective_images_rejected(rgb, reason):
    result = assess(rgb)
    assert result.status == "rejected"
    assert reason in {f.code for f in result.findings}
    assert all(np.isfinite(v) for v in result.metrics.values())


def test_glare_requires_review():
    rgb = photograph()
    rgb[:120, :160] = 255
    result = assess(rgb)
    assert result.status == "indeterminate"
    assert "possible-glare" in {f.code for f in result.findings}


def test_noise_requires_review():
    rng = np.random.default_rng(42)
    noisy = np.clip(photograph().astype(float) + rng.normal(0, 45, (480, 640, 1)), 0, 255).astype(np.uint8)
    result = assess(noisy)
    assert result.status != "accepted"
    assert "possible-noise" in {f.code for f in result.findings}


def test_large_image_is_bounded_and_deterministic():
    rgb = photograph(2000, 1600)
    first = assess(rgb)
    assert first == assess(rgb)
    assert first.metrics["width"] == 2000
    assert first.metrics["analysis-width"] == POLICY.analysis_long_side


@pytest.mark.parametrize("fmt", ["PNG", "JPEG"])
def test_valid_decoding(fmt):
    decoded = decode_attachment(attachment(fmt=fmt))
    assert decoded.rgb.shape == (480, 640, 3)
    assert not decoded.monochrome


def test_exif_orientation_applied_and_metadata_discarded():
    exif = Image.Exif()
    exif[274] = 6
    exif[315] = "private-author-must-not-leak"
    decoded = decode_attachment(attachment(fmt="JPEG", exif=exif))
    assert (decoded.width, decoded.height) == (480, 640)
    assert set(decoded.__dict__) == {"rgb", "width", "height", "monochrome"}


@pytest.mark.parametrize(
    "image,status",
    [
        ({"contentType": "image/png", "url": "http://169.254.169.254"}, 400),
        ({"contentType": "image/svg+xml", "data": "abcd"}, 415),
        ({"contentType": "image/png", "data": "not base64!"}, 400),
        ({"contentType": "image/png", "data": ""}, 400),
        ({"contentType": "image/png", "data": "aGVsbG8="}, 422),
        ({"contentType": "image/png", "data": 42}, 400),
        ([], 400),
    ],
)
def test_invalid_attachments(image, status):
    with pytest.raises(ImageInputError) as exc:
        decode_attachment(image)
    assert exc.value.status == status


def test_mime_mismatch_and_truncation_rejected():
    image = attachment(fmt="JPEG")
    image["contentType"] = "image/png"
    with pytest.raises(ImageInputError, match="tipo declarado"):
        decode_attachment(image)
    image = attachment()
    raw = base64.b64decode(image["data"])
    image["data"] = base64.b64encode(raw[: len(raw) // 2]).decode()
    with pytest.raises(ImageInputError):
        decode_attachment(image)


def test_pixel_limit_checked_before_full_decode(monkeypatch):
    from src.image_quality import decoder

    monkeypatch.setattr(decoder, "MAX_IMAGE_PIXELS", 100)
    image = attachment()
    monkeypatch.setattr(Image.Image, "load", lambda self, *a, **kw: pytest.fail("decoded before dimension check"))
    with pytest.raises(ImageInputError) as exc:
        decode_attachment(image)
    assert exc.value.status == 413


def test_byte_limit_before_base64_allocation(monkeypatch):
    from src.image_quality import decoder

    monkeypatch.setattr(decoder, "MAX_IMAGE_BYTES", 3)
    with pytest.raises(ImageInputError) as exc:
        decode_attachment(attachment())
    assert exc.value.status == 413


def test_animated_and_transparent_images_rejected():
    animated = attachment(save_all=True, append_images=[Image.fromarray(photograph() // 2)], duration=100, loop=0)
    with pytest.raises(ImageInputError, match="único quadro"):
        decode_attachment(animated)
    rgba = np.dstack((photograph(), np.full((480, 640), 100, dtype=np.uint8)))
    with pytest.raises(ImageInputError, match="transparentes"):
        decode_attachment(attachment(rgba))


def test_success_fhir_response_and_no_retained_image(client):
    body = payload()
    response = post(client, body)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.mimetype == "application/fhir+json"
    assert value(response.json, "status") == "accepted"
    assert value(response.json, "validationStage") == "experimental"
    observation = value(response.json, "measurement")
    assert observation["resourceType"] == "Observation"
    assert observation["status"] == "final"
    assert "subject" not in observation and "id" not in observation
    assert len(observation["component"]) == 12
    text = response.get_data(as_text=True)
    assert body["parameter"][2]["valueAttachment"]["data"] not in text
    assert "clinician" not in text
    request_id = response.headers["X-Request-ID"]
    assert str(uuid.UUID(request_id)) == request_id
    assert value(response.json, "requestId") == f"urn:uuid:{request_id}"
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("consent", [False, None, "true", 1])
def test_consent_is_mandatory_before_decoding(client, monkeypatch, consent):
    from apps.api.routes import image_quality

    body = payload()
    body["parameter"][1]["valueBoolean"] = consent
    monkeypatch.setattr(image_quality, "decode_attachment", lambda _: pytest.fail("decoded without consent"))
    assert_outcome(post(client, body), 403)


@pytest.mark.parametrize(
    "token,status", [(None, 401), ("expired", 401), ("researcher", 403), ("patient", 403), ("unknown", 403)]
)
def test_authentication_authorization(client, token, status):
    headers = {"Content-Type": "application/fhir+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = post(client, headers=headers)
    assert_outcome(response, status)
    assert "secret-token" not in response.get_data(as_text=True)


def test_authentication_disabled_does_not_bypass_operation(client, monkeypatch):
    monkeypatch.setenv("CLINICAL_API_REQUIRE_AUTH", "0")
    assert_outcome(post(client), 503)


def test_missing_auth_backend_fails_closed(client):
    client.application.config["REDISUS_AUTH_VERIFIER"] = None
    client.application.extensions["redisus_auth_verifier"] = None
    assert_outcome(post(client), 503)


def test_firebase_checks_revocation(client):
    class Verifier:
        checked = False

        def verify_id_token(self, token, *, check_revoked=False):
            self.checked = check_revoked
            raise ValueError("revoked-token-private")

    verifier = Verifier()
    client.application.config["REDISUS_AUTH_VERIFIER"] = verifier
    assert_outcome(post(client), 401)
    assert verifier.checked


def test_request_id_never_reflects_client_header(client):
    response = post(client, headers={**HEADERS, "X-Request-ID": "private-patient-name"})
    assert response.status_code == 200
    assert "private-patient-name" not in response.get_data(as_text=True)
    assert str(uuid.UUID(response.headers["X-Request-ID"])) == response.headers["X-Request-ID"]


def test_http_limit_returns_fhir_outcome(client):
    client.application.config["MAX_CONTENT_LENGTH"] = 100
    assert_outcome(post(client), 413)


def test_wrong_fhir_version_is_rejected(client):
    assert_outcome(post(client, headers={**HEADERS, "Content-Type": "application/fhir+json; fhirVersion=5.0"}), 415)


def test_preflight_does_not_require_token(client):
    response = client.options(
        ENDPOINT, headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"}
    )
    assert response.status_code == 200


def test_transient_slots_released_after_invalid_input(client):
    for _ in range(3):
        assert_outcome(client.post(ENDPOINT, data="{", headers=HEADERS), 400)
    assert post(client).status_code == 200


def test_switching_users_does_not_reuse_authorization(client):
    assert post(client).status_code == 200
    assert_outcome(post(client, headers={**HEADERS, "Authorization": "Bearer patient"}), 403)
    assert_outcome(post(client, headers={"Content-Type": "application/fhir+json"}), 401)
    assert post(client, headers={**HEADERS, "Authorization": "Bearer nurse"}).status_code == 200


@pytest.mark.parametrize(
    "mutation",
    [
        lambda b: b.update(subject={"reference": "Patient/private"}),
        lambda b: b["parameter"].append(copy.deepcopy(b["parameter"][0])),
        lambda b: b["parameter"][0].update(valueString="patient/name"),
        lambda b: b["parameter"][0].update(valueString="x"),
        lambda b: b["parameter"][0].update(valueString=44),
        lambda b: b["parameter"][0].update(valueBoolean=True),
        lambda b: b["parameter"][0].update(name="patientId"),
        lambda b: b["parameter"][0].update(name=[]),
        lambda b: b.update(parameter=[]),
        lambda b: b.update(resourceType="Bundle"),
    ],
)
def test_strict_request_contract(client, mutation):
    body = payload()
    mutation(body)
    assert_outcome(post(client, body), 400)


@pytest.mark.parametrize(
    "raw", [b"", b"null", b"[]", b"{", b'{"resourceType":"Parameters","resourceType":"Parameters"}', b"NaN", b"\xff"]
)
def test_malformed_json_is_safe(client, raw):
    assert_outcome(client.post(ENDPOINT, data=raw, headers=HEADERS), 400)


def test_rejected_quality_is_a_successful_operation(client):
    response = post(client, payload(attachment(np.zeros((480, 640, 3), dtype=np.uint8))))
    assert response.status_code == 200
    assert value(response.json, "status") == "rejected"
    assert any(p["name"] == "reason" for p in response.json["parameter"])


def test_monochrome_requires_review(client):
    gray = cv2.cvtColor(photograph(), cv2.COLOR_RGB2GRAY)
    response = post(client, payload(attachment(gray)))
    assert value(response.json, "status") == "indeterminate"


def test_content_negotiation_and_methods(client):
    assert_outcome(post(client, headers={**HEADERS, "Content-Type": "application/json"}), 415)
    assert_outcome(post(client, headers={**HEADERS, "Accept": "application/fhir+xml"}), 406)
    assert_outcome(post(client, headers={**HEADERS, "Content-Encoding": "gzip"}), 415)
    assert_outcome(client.get(ENDPOINT, headers=HEADERS), 405)
    assert_outcome(client.get("/api/v1/fhir/missing", headers=HEADERS), 404)
    assert_outcome(client.post(ENDPOINT + "?patient=private", json=payload(), headers=HEADERS), 400)


def test_body_limit_and_busy_slots(client, monkeypatch):
    from apps.api.routes import image_quality

    monkeypatch.setattr(image_quality, "MAX_REQUEST_BYTES", 100)
    assert_outcome(post(client), 413)
    monkeypatch.setattr(image_quality, "MAX_REQUEST_BYTES", 14 * 1024 * 1024)
    slots = client.application.extensions["image_quality_slots"]
    assert slots.acquire(False) and slots.acquire(False)
    try:
        response = post(client)
        assert_outcome(response, 429)
        assert response.headers["Retry-After"]
    finally:
        slots.release()
        slots.release()
    assert post(client).status_code == 200


def test_rate_limit_is_per_user(client, monkeypatch):
    monkeypatch.setenv("REDISUS_RATE_LIMIT_IMAGE_QUALITY", "1")
    assert post(client).status_code == 200
    assert_outcome(post(client), 429)
    assert post(client, headers={**HEADERS, "Authorization": "Bearer doctor"}).status_code == 200


def test_unexpected_error_is_sanitized_and_releases_capacity(client, monkeypatch, caplog):
    from apps.api.routes import image_quality

    original = image_quality.assess_image

    def fail(_):
        raise RuntimeError("patient-data-secret")

    monkeypatch.setattr(image_quality, "assess_image", fail)
    for _ in range(3):
        response = post(client)
        assert_outcome(response, 500)
        assert "patient-data-secret" not in response.get_data(as_text=True)
    assert "patient-data-secret" not in caplog.text
    monkeypatch.setattr(image_quality, "assess_image", original)
    assert post(client).status_code == 200


def test_metadata_describes_the_actual_operation(client):
    metadata = client.get("/api/v1/fhir/metadata", headers=HEADERS)
    definition = client.get("/api/v1/fhir/OperationDefinition/validate-image", headers=HEADERS)
    assert metadata.status_code == definition.status_code == 200
    assert metadata.json["fhirVersion"] == "4.0.1"
    assert metadata.json["rest"][0]["operation"][0]["definition"] == definition.json["url"]
    assert definition.json["affectsState"] is False
    assert definition.json["system"] is True
    inputs = {p["name"] for p in definition.json["parameter"] if p["use"] == "in"}
    assert inputs == {"imageId", "consent", "image"}
    assert parse_parameters(payload())[0] == "synthetic-image-001"
