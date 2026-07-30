from __future__ import annotations

import re
from typing import Any, Mapping
from urllib.parse import urlparse

import requests

from ...client.base import AbstractFHIRClient
from .auth import RNDSTokenProvider
from .config import RNDSSettings
from .exceptions import (
    RNDSAuthenticationError,
    RNDSBundleValidationError,
    RNDSServerRejectedError,
    RNDSUnknownSubmissionStateError,
    RNDSUnsupportedOperationError,
)
from .validation import validate_rnds_document_bundle


_RESOURCE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,63}$")
_RESOURCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SEARCH_PARAMETER = re.compile(r"^_?[A-Za-z][A-Za-z0-9._-]{0,63}$")
_PROFESSIONAL_IDENTIFIER = re.compile(r"^(?:\d{11}|\d{15})$")
_ALLOWED_READ_RESOURCES = frozenset({"Bundle", "Organization", "Patient", "Practitioner", "PractitionerRole"})
_FHIR_ISSUE_CODES = frozenset(
    {
        "business-rule",
        "code-invalid",
        "conflict",
        "deleted",
        "duplicate",
        "exception",
        "expired",
        "extension",
        "forbidden",
        "incomplete",
        "informational",
        "invalid",
        "invariant",
        "lock-error",
        "login",
        "multiple-matches",
        "no-store",
        "not-found",
        "not-supported",
        "processing",
        "required",
        "security",
        "structure",
        "suppressed",
        "throttled",
        "timeout",
        "too-costly",
        "too-long",
        "transient",
        "unknown",
        "value",
    }
)


class RNDSFHIRAdapter(AbstractFHIRClient):
    """Server-side RNDS adapter. Create one instance per professional context."""

    def __init__(
        self,
        settings: RNDSSettings,
        *,
        professional_cns_or_cpf: str,
        strict_validation: bool = True,
        session: requests.Session | None = None,
        token_provider: RNDSTokenProvider | None = None,
    ):
        super().__init__(strict_validation=strict_validation)
        professional_identifier = str(professional_cns_or_cpf).strip()
        if not _PROFESSIONAL_IDENTIFIER.fullmatch(professional_identifier):
            raise RNDSBundleValidationError("RNDS professional identifier must be a valid CNS or CPF shape")

        self.settings = settings
        self.professional_cns_or_cpf = professional_identifier
        self.session = session or requests.Session()
        self.token_provider = token_provider or RNDSTokenProvider(settings)
        self.server_url = settings.bundle_url

    @classmethod
    def from_environment(
        cls,
        *,
        professional_cns_or_cpf: str,
        strict_validation: bool = True,
    ) -> "RNDSFHIRAdapter":
        return cls(
            RNDSSettings.from_environment(),
            professional_cns_or_cpf=professional_cns_or_cpf,
            strict_validation=strict_validation,
        )

    @property
    def destination(self) -> str:
        return self.server_url

    def send_resource(self, resource: Mapping[str, Any]) -> dict[str, Any]:
        raise RNDSUnsupportedOperationError("RNDS clinical document submission only accepts a document Bundle")

    def send_bundle(self, bundle: Mapping[str, Any]) -> dict[str, Any]:
        self.validate_bundle_before_send(bundle)
        validate_rnds_document_bundle(bundle, self.settings)

        response = self._request("POST", self.settings.bundle_url, json=dict(bundle))
        if response.status_code != 201:
            raise RNDSServerRejectedError(
                response.status_code,
                _operation_outcome_codes(response),
            )

        location = str(response.headers.get("Location") or response.headers.get("Content-Location") or "").strip()
        if not _valid_location(location, allowed_host=urlparse(self.settings.ehr_base_url).netloc):
            raise RNDSUnknownSubmissionStateError(
                "RNDS accepted the Bundle without a valid Location header; reconcile before retrying"
            )

        return {
            "resourceType": "Bundle",
            "type": "transaction-response",
            "entry": [
                {
                    "response": {
                        "status": "201 Created",
                        "location": location,
                    }
                }
            ],
        }

    def read(self, resource_type: str, resource_id: str) -> dict[str, Any] | None:
        resource_name = self._validated_resource_name(resource_type)
        identifier = str(resource_id).strip()
        if not _RESOURCE_ID.fullmatch(identifier):
            raise RNDSUnsupportedOperationError("RNDS resource identifier has an invalid format")
        response = self._request("GET", f"{self.settings.fhir_base_url}/{resource_name}/{identifier}")
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise RNDSServerRejectedError(response.status_code, _operation_outcome_codes(response))
        return _json_mapping(response)

    def search(self, resource_type: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        resource_name = self._validated_resource_name(resource_type)
        safe_params: dict[str, str | int | float | bool] = {}
        for key, value in dict(params or {}).items():
            key_text = str(key).strip()
            if not _SEARCH_PARAMETER.fullmatch(key_text) or not isinstance(value, (str, int, float, bool)):
                raise RNDSUnsupportedOperationError("RNDS search parameters contain an unsupported value")
            safe_params[key_text] = value

        response = self._request(
            "GET",
            f"{self.settings.fhir_base_url}/{resource_name}",
            params=safe_params,
        )
        if response.status_code != 200:
            raise RNDSServerRejectedError(response.status_code, _operation_outcome_codes(response))
        return _json_mapping(response)

    def should_retry(self, error: Exception) -> bool:
        return isinstance(error, RNDSAuthenticationError)

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        response = self._request_once(method, url, force_refresh=False, **kwargs)
        if response.status_code != 401:
            return response

        # A 401 means RNDS rejected the request before accepting the clinical
        # document. Refreshing the token once is safe; all other retries require
        # explicit reconciliation by the operator.
        self.token_provider.invalidate()
        return self._request_once(method, url, force_refresh=True, **kwargs)

    def _request_once(
        self,
        method: str,
        url: str,
        *,
        force_refresh: bool,
        **kwargs: Any,
    ) -> requests.Response:
        token = self.token_provider.access_token(force_refresh=force_refresh)
        headers = {
            "Accept": "application/fhir+json",
            "Authorization": self.professional_cns_or_cpf,
            "X-Authorization-Server": f"Bearer {token}",
        }
        if method.upper() == "POST":
            headers["Content-Type"] = "application/fhir+json"
        try:
            return self.session.request(
                method,
                url,
                headers=headers,
                timeout=self.settings.timeout_seconds,
                verify=self.settings.tls_verify,
                **kwargs,
            )
        except requests.RequestException as exc:
            if method.upper() == "POST":
                raise RNDSUnknownSubmissionStateError(
                    "RNDS submission response was not received; reconcile before retrying"
                ) from exc
            raise RNDSServerRejectedError(503) from exc

    @staticmethod
    def _validated_resource_name(resource_type: str) -> str:
        resource_name = str(resource_type).strip()
        if not _RESOURCE_NAME.fullmatch(resource_name) or resource_name not in _ALLOWED_READ_RESOURCES:
            raise RNDSUnsupportedOperationError("RNDS resource type is not supported by this connector")
        return resource_name


def _operation_outcome_codes(response: requests.Response) -> tuple[str, ...]:
    try:
        payload = response.json()
    except (TypeError, ValueError):
        return ()
    if not isinstance(payload, Mapping) or payload.get("resourceType") != "OperationOutcome":
        return ()

    codes: list[str] = []
    issues = payload.get("issue")
    if isinstance(issues, list):
        for issue in issues[:20]:
            if not isinstance(issue, Mapping):
                continue
            code = str(issue.get("code") or "").strip()
            if code in _FHIR_ISSUE_CODES and code not in codes:
                codes.append(code)
    return tuple(codes)


def _json_mapping(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except (TypeError, ValueError) as exc:
        raise RNDSServerRejectedError(response.status_code) from exc
    if not isinstance(payload, Mapping):
        raise RNDSServerRejectedError(response.status_code)
    return dict(payload)


def _valid_location(location: str, *, allowed_host: str) -> bool:
    if not location or len(location) > 500:
        return False
    parsed = urlparse(location)
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        return False
    if parsed.scheme or parsed.netloc:
        return (
            parsed.scheme == "https"
            and parsed.netloc == allowed_host
            and bool(parsed.path.rstrip("/").rsplit("/", 1)[-1])
        )
    return location.startswith("/") and bool(location.rstrip("/").rsplit("/", 1)[-1])
