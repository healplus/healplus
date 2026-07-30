from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import requests

from src.interoperability.fhir_r4 import (
    FHIRPublicationAuthorization,
    FHIRPublicationError,
    FHIRPublicationService,
)
from src.interoperability.fhir_r4.adapters.rnds import (
    RNDSAuthenticationError,
    RNDSBundleValidationError,
    RNDSConfigurationError,
    RNDSEnvironment,
    RNDSFHIRAdapter,
    RNDSServerRejectedError,
    RNDSSettings,
    RNDSTokenProvider,
)


DOCUMENT_PROFILE = "http://www.saude.gov.br/fhir/r4/StructureDefinition/BRRegistroAtendimentoClinico-1.0"
PROFESSIONAL_CNS = "123456789012345"


@dataclass
class FakeResponse:
    status_code: int
    payload: Any = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        return self.payload


class FakeAuthSession:
    def __init__(self, responses: list[FakeResponse]):
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return self.responses.pop(0)


class FakeEHRSession:
    def __init__(self, responses: list[FakeResponse | Exception]):
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeTokenProvider:
    def __init__(self, tokens: list[str]):
        self.tokens = list(tokens)
        self.calls: list[bool] = []
        self.invalidations = 0

    def access_token(self, *, force_refresh: bool = False) -> str:
        self.calls.append(force_refresh)
        return self.tokens.pop(0)

    def invalidate(self) -> None:
        self.invalidations += 1


def _settings(tmp_path: Path, **changes: Any) -> RNDSSettings:
    certificate = tmp_path / "client-certificate.pem"
    private_key = tmp_path / "client-private-key.pem"
    certificate.write_text("synthetic certificate", encoding="utf-8")
    private_key.write_text("synthetic private key", encoding="utf-8")
    values = {
        "environment": RNDSEnvironment.HOMOLOGATION,
        "requester_identifier": "14008",
        "certificate_pem_path": certificate,
        "private_key_pem_path": private_key,
        "document_profiles": (DOCUMENT_PROFILE,),
    }
    values.update(changes)
    return RNDSSettings(**values)


def _document_bundle(settings: RNDSSettings) -> dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "id": "synthetic-rac-001",
        "type": "document",
        "identifier": {
            "system": settings.bundle_identifier_system,
            "value": "synthetic-rac-001",
        },
        "timestamp": "2026-07-29T12:00:00-03:00",
        "entry": [
            {
                "fullUrl": "urn:uuid:synthetic-composition",
                "resource": {
                    "resourceType": "Composition",
                    "meta": {"profile": [DOCUMENT_PROFILE]},
                    "status": "final",
                    "type": {"text": "Synthetic RAC"},
                    "date": "2026-07-29T12:00:00-03:00",
                    "title": "Synthetic clinical document",
                    "author": [{"display": "Synthetic health organization"}],
                },
            }
        ],
    }


def _authorization(adapter: RNDSFHIRAdapter) -> FHIRPublicationAuthorization:
    return FHIRPublicationAuthorization(
        actor_id="synthetic-professional",
        consent_reference="synthetic-consent",
        consent_scope="fhir_publication",
        destination=adapter.destination,
        purpose="technical_homologation",
        rollback_reference="synthetic-reconciliation-runbook",
        user_action_confirmed=True,
        institution_approved=True,
    )


def test_homologation_settings_use_official_hosts_and_absolute_secret_files(tmp_path: Path):
    settings = _settings(tmp_path)

    assert settings.token_url == "https://ehr-auth-hmg.saude.gov.br/api/token"
    assert settings.bundle_url == "https://ehr-services.hmg.saude.gov.br/api/fhir/r4/Bundle"
    assert settings.client_certificate == (
        str((tmp_path / "client-certificate.pem").resolve()),
        str((tmp_path / "client-private-key.pem").resolve()),
    )
    assert settings.tls_verify is True


def test_production_requires_approval_and_state(tmp_path: Path):
    with pytest.raises(RNDSConfigurationError, match="institutional approval"):
        _settings(
            tmp_path,
            environment=RNDSEnvironment.PRODUCTION,
            state="SP",
        )

    settings = _settings(
        tmp_path,
        environment=RNDSEnvironment.PRODUCTION,
        state="SP",
        production_approved=True,
    )
    assert settings.token_url == "https://ehr-auth.saude.gov.br/api/token"
    assert settings.bundle_url == "https://sp-ehr-services.saude.gov.br/api/fhir/r4/Bundle"


def test_token_provider_uses_mtls_only_for_auth_and_caches_millisecond_expiration(tmp_path: Path):
    settings = _settings(tmp_path)
    auth_session = FakeAuthSession(
        [
            FakeResponse(200, {"access_token": "token-one", "expires_in": 1_800_000}),
            FakeResponse(200, {"access_token": "token-two", "expires_in": 1_800_000}),
        ]
    )
    now = [100.0]
    provider = RNDSTokenProvider(
        settings,
        session=auth_session,
        monotonic=lambda: now[0],
    )

    assert provider.access_token() == "token-one"
    assert provider.access_token() == "token-one"
    assert len(auth_session.calls) == 1
    assert auth_session.calls[0]["cert"] == settings.client_certificate
    assert auth_session.calls[0]["verify"] is True

    now[0] += 1_771
    assert provider.access_token() == "token-two"
    assert len(auth_session.calls) == 2


def test_authentication_error_does_not_include_response_body_or_token(tmp_path: Path):
    settings = _settings(tmp_path)
    provider = RNDSTokenProvider(
        settings,
        session=FakeAuthSession([FakeResponse(500, {"access_token": "must-not-leak"})]),
    )

    with pytest.raises(RNDSAuthenticationError) as captured:
        provider.access_token()

    assert "must-not-leak" not in str(captured.value)


def test_adapter_submits_document_with_rnds_headers_and_returns_location(tmp_path: Path):
    settings = _settings(tmp_path)
    ehr_session = FakeEHRSession(
        [
            FakeResponse(
                201,
                headers={"Location": ("https://ehr-services.hmg.saude.gov.br/api/fhir/r4/Bundle/synthetic-rnds-id")},
            )
        ]
    )
    token_provider = FakeTokenProvider(["synthetic-access-token"])
    adapter = RNDSFHIRAdapter(
        settings,
        professional_cns_or_cpf=PROFESSIONAL_CNS,
        session=ehr_session,
        token_provider=token_provider,
    )

    result = adapter.send_bundle(_document_bundle(settings))

    assert result["entry"][0]["response"]["status"] == "201 Created"
    call = ehr_session.calls[0]
    assert call["url"] == settings.bundle_url
    assert call["headers"]["X-Authorization-Server"] == "Bearer synthetic-access-token"
    assert call["headers"]["Authorization"] == PROFESSIONAL_CNS
    assert "cert" not in call


def test_adapter_refreshes_expired_token_once_after_401(tmp_path: Path):
    settings = _settings(tmp_path)
    ehr_session = FakeEHRSession(
        [
            FakeResponse(401),
            FakeResponse(201, headers={"Content-Location": "/api/fhir/r4/Bundle/synthetic-rnds-id"}),
        ]
    )
    token_provider = FakeTokenProvider(["expired-token", "fresh-token"])
    adapter = RNDSFHIRAdapter(
        settings,
        professional_cns_or_cpf=PROFESSIONAL_CNS,
        session=ehr_session,
        token_provider=token_provider,
    )

    adapter.send_bundle(_document_bundle(settings))

    assert token_provider.calls == [False, True]
    assert token_provider.invalidations == 1
    assert len(ehr_session.calls) == 2
    assert ehr_session.calls[1]["headers"]["X-Authorization-Server"] == "Bearer fresh-token"


def test_adapter_blocks_generic_heal_plus_bundle_before_authentication(tmp_path: Path):
    settings = _settings(tmp_path)
    ehr_session = FakeEHRSession([])
    token_provider = FakeTokenProvider([])
    adapter = RNDSFHIRAdapter(
        settings,
        professional_cns_or_cpf=PROFESSIONAL_CNS,
        session=ehr_session,
        token_provider=token_provider,
    )
    bundle = _document_bundle(settings)
    bundle["type"] = "transaction"

    with pytest.raises(RNDSBundleValidationError, match="type=document"):
        adapter.send_bundle(bundle)

    assert token_provider.calls == []
    assert ehr_session.calls == []


def test_adapter_sanitizes_operation_outcome_diagnostics(tmp_path: Path):
    settings = _settings(tmp_path)
    ehr_session = FakeEHRSession(
        [
            FakeResponse(
                422,
                {
                    "resourceType": "OperationOutcome",
                    "issue": [
                        {
                            "code": "processing",
                            "diagnostics": "sensitive patient identifier 999999999999999",
                        }
                    ],
                },
            )
        ]
    )
    adapter = RNDSFHIRAdapter(
        settings,
        professional_cns_or_cpf=PROFESSIONAL_CNS,
        session=ehr_session,
        token_provider=FakeTokenProvider(["synthetic-token"]),
    )

    with pytest.raises(RNDSServerRejectedError) as captured:
        adapter.send_bundle(_document_bundle(settings))

    assert captured.value.outcome_codes == ("processing",)
    assert "999999999999999" not in str(captured.value)


def test_publication_does_not_retry_ambiguous_rnds_submission(tmp_path: Path):
    settings = _settings(tmp_path)
    ehr_session = FakeEHRSession([requests.ConnectionError("synthetic network interruption")])
    adapter = RNDSFHIRAdapter(
        settings,
        professional_cns_or_cpf=PROFESSIONAL_CNS,
        session=ehr_session,
        token_provider=FakeTokenProvider(["secret-token"]),
    )
    service = FHIRPublicationService(
        adapter,
        audit_dir=tmp_path / "audit",
        max_retries=3,
        retry_delay_seconds=0,
    )

    with pytest.raises(FHIRPublicationError, match="after 1 attempts"):
        service.publish_bundle(
            _document_bundle(settings),
            authorization=_authorization(adapter),
        )

    assert len(ehr_session.calls) == 1
    audit_text = (tmp_path / "audit" / "publication_audit.jsonl").read_text(encoding="utf-8")
    assert "secret-token" not in audit_text
    assert PROFESSIONAL_CNS not in audit_text
    assert "synthetic network interruption" not in audit_text
