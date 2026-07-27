from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from src.interoperability.fhir_r4 import (
    FHIRPublicationAuthorization,
    FHIRPublicationError,
    FHIRPublicationService,
    RedisusFHIRMapper,
)
from src.interoperability.fhir_r4.client import AbstractFHIRClient
from src.interoperability.fhir_r4.examples import (
    sample_care_plan_data,
    sample_evaluation_data,
    sample_inference_result,
    sample_patient_data,
)


class RecordingFHIRClient(AbstractFHIRClient):
    def __init__(self, *, failures_before_success: int = 0):
        super().__init__(strict_validation=False)
        self.server_url = "https://example.org/fhir"
        self.failures_before_success = failures_before_success
        self.sent_bundles: list[dict[str, Any]] = []

    def send_resource(self, resource: Mapping[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def send_bundle(self, bundle: Mapping[str, Any]) -> dict[str, Any]:
        self.sent_bundles.append(dict(bundle))
        if self.failures_before_success > 0:
            self.failures_before_success -= 1
            raise RuntimeError("temporary upstream failure")
        return {
            "resourceType": "Bundle",
            "type": "transaction-response",
            "entry": [{"response": {"status": "200 OK"}}],
        }

    def read(self, resource_type: str, resource_id: str) -> dict[str, Any] | None:
        return None

    def search(self, resource_type: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return {"resourceType": "Bundle", "type": "searchset", "entry": []}


class PartialThenSuccessfulFHIRClient(RecordingFHIRClient):
    def send_bundle(self, bundle: Mapping[str, Any]) -> dict[str, Any]:
        self.sent_bundles.append(dict(bundle))
        if len(self.sent_bundles) == 1:
            return {
                "resourceType": "Bundle",
                "type": "transaction-response",
                "entry": [
                    {"response": {"status": "201 Created"}},
                    {"response": {"status": "500 Internal Server Error"}},
                ],
            }
        return {
            "resourceType": "Bundle",
            "type": "transaction-response",
            "entry": [{"response": {"status": "200 OK"}}],
        }


def _build_bundle() -> dict[str, Any]:
    mapper = RedisusFHIRMapper(strict_validation=False)
    return mapper.map_case_to_bundle(
        patient_data=sample_patient_data(),
        evaluation_data=sample_evaluation_data(),
        inference_result=sample_inference_result(),
        care_plan_data=sample_care_plan_data(),
        bundle_type="transaction",
    )


def _authorization() -> FHIRPublicationAuthorization:
    return FHIRPublicationAuthorization(
        actor_id="synthetic-user-a",
        consent_reference="synthetic-consent-1",
        consent_scope="fhir_publication",
        destination="https://example.org/fhir",
        purpose="technical_validation",
        rollback_reference="synthetic-rollback-1",
        user_action_confirmed=True,
        institution_approved=True,
    )


def test_publication_service_is_idempotent_for_same_logical_bundle(tmp_path: Path):
    client = RecordingFHIRClient()
    service = FHIRPublicationService(client, audit_dir=tmp_path / "audit", retry_delay_seconds=0)

    first_bundle = _build_bundle()
    second_bundle = _build_bundle()

    first = service.publish_bundle(
        first_bundle,
        case_id="lesion-venous-001",
        evaluation_id="evaluation-2026-04-19-001",
        authorization=_authorization(),
    )
    second = service.publish_bundle(
        second_bundle,
        case_id="lesion-venous-001",
        evaluation_id="evaluation-2026-04-19-001",
        authorization=_authorization(),
    )

    assert first.status == "published"
    assert second.status == "skipped"
    assert len(client.sent_bundles) == 1
    assert first.idempotency_key == second.idempotency_key

    audit_events = [
        json.loads(line)
        for line in (tmp_path / "audit" / "publication_audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert {event["event_type"] for event in audit_events} >= {"attempt_started", "published", "idempotent_skip"}


def test_publication_service_retries_before_succeeding(tmp_path: Path):
    client = RecordingFHIRClient(failures_before_success=1)
    service = FHIRPublicationService(client, audit_dir=tmp_path / "audit", retry_delay_seconds=0)

    result = service.publish_bundle(
        _build_bundle(),
        case_id="lesion-venous-001",
        evaluation_id="evaluation-2026-04-19-001",
        authorization=_authorization(),
    )

    assert result.status == "published"
    assert result.attempts == 2
    assert len(client.sent_bundles) == 2

    audit_events = [
        json.loads(line)
        for line in (tmp_path / "audit" / "publication_audit.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert any(event["event_type"] == "attempt_failed" for event in audit_events)


def test_publication_service_retries_partial_response_before_marking_published(tmp_path: Path):
    client = PartialThenSuccessfulFHIRClient()
    service = FHIRPublicationService(client, audit_dir=tmp_path / "audit", retry_delay_seconds=0)

    result = service.publish_bundle(_build_bundle(), authorization=_authorization())

    assert result.status == "published"
    assert result.attempts == 2
    state = json.loads((tmp_path / "audit" / "publication_index.json").read_text(encoding="utf-8"))
    assert state[result.idempotency_key]["attempts"] == 2
    audit_text = (tmp_path / "audit" / "publication_audit.jsonl").read_text(encoding="utf-8")
    assert "500 Internal Server Error" not in audit_text
    assert '"event_type": "attempt_failed"' in audit_text


def test_publication_service_raises_after_exhausting_retries(tmp_path: Path):
    client = RecordingFHIRClient(failures_before_success=3)
    service = FHIRPublicationService(client, audit_dir=tmp_path / "audit", max_retries=1, retry_delay_seconds=0)

    with pytest.raises(FHIRPublicationError):
        service.publish_bundle(
            _build_bundle(),
            case_id="lesion-venous-001",
            evaluation_id="evaluation-2026-04-19-001",
            authorization=_authorization(),
        )

    assert len(client.sent_bundles) == 2


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"user_action_confirmed": False}, "explicit user action"),
        ({"institution_approved": False}, "institutional approval"),
        ({"consent_scope": "export_only"}, "consent scope"),
        ({"destination": "https://other.example/fhir"}, "destination"),
    ],
)
def test_publication_fails_closed_without_complete_authorization(tmp_path: Path, changes, message):
    client = RecordingFHIRClient()
    service = FHIRPublicationService(client, audit_dir=tmp_path / "audit", retry_delay_seconds=0)
    authorization = _authorization()
    invalid = FHIRPublicationAuthorization(
        **{
            "actor_id": authorization.actor_id,
            "consent_reference": authorization.consent_reference,
            "consent_scope": authorization.consent_scope,
            "destination": authorization.destination,
            "purpose": authorization.purpose,
            "rollback_reference": authorization.rollback_reference,
            "user_action_confirmed": authorization.user_action_confirmed,
            "institution_approved": authorization.institution_approved,
            **changes,
        }
    )

    with pytest.raises(FHIRPublicationError, match=message):
        service.publish_bundle(_build_bundle(), authorization=invalid)

    assert client.sent_bundles == []


def test_publication_audit_does_not_persist_bundle_or_upstream_error_detail(tmp_path: Path):
    client = RecordingFHIRClient(failures_before_success=1)
    service = FHIRPublicationService(client, audit_dir=tmp_path / "audit", max_retries=0, retry_delay_seconds=0)

    with pytest.raises(FHIRPublicationError):
        service.publish_bundle(
            _build_bundle(),
            authorization=_authorization(),
            metadata={"purpose": "technical_validation"},
        )

    audit_text = (tmp_path / "audit" / "publication_audit.jsonl").read_text(encoding="utf-8")
    assert "temporary upstream failure" not in audit_text
    assert '"resourceType": "Patient"' not in audit_text
    assert "RuntimeError" in audit_text


@pytest.mark.parametrize(
    "target",
    [
        "http://example.org/fhir",
        "https://user:secret@example.org/fhir",
        "https://example.org/fhir?token=secret",
        "https://example.org/fhir#fragment",
    ],
)
def test_publication_rejects_insecure_or_sensitive_target(tmp_path: Path, target: str):
    client = RecordingFHIRClient()
    client.server_url = target
    service = FHIRPublicationService(client, audit_dir=tmp_path / "audit", retry_delay_seconds=0)
    authorization = _authorization()
    matching_authorization = FHIRPublicationAuthorization(
        actor_id=authorization.actor_id,
        consent_reference=authorization.consent_reference,
        consent_scope=authorization.consent_scope,
        destination=target,
        purpose=authorization.purpose,
        rollback_reference=authorization.rollback_reference,
        user_action_confirmed=authorization.user_action_confirmed,
        institution_approved=authorization.institution_approved,
    )

    with pytest.raises(FHIRPublicationError):
        service.publish_bundle(_build_bundle(), authorization=matching_authorization)

    assert client.sent_bundles == []
