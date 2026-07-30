from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

from .exceptions import RNDSConfigurationError


class RNDSEnvironment(str, Enum):
    HOMOLOGATION = "homologation"
    PRODUCTION = "production"


_REQUESTER_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_BRAZILIAN_STATES = frozenset(
    {
        "AC",
        "AL",
        "AP",
        "AM",
        "BA",
        "CE",
        "DF",
        "ES",
        "GO",
        "MA",
        "MT",
        "MS",
        "MG",
        "PA",
        "PB",
        "PR",
        "PE",
        "PI",
        "RJ",
        "RN",
        "RS",
        "RO",
        "RR",
        "SC",
        "SP",
        "SE",
        "TO",
    }
)


@dataclass(frozen=True, slots=True)
class RNDSSettings:
    environment: RNDSEnvironment
    requester_identifier: str
    certificate_pem_path: Path
    private_key_pem_path: Path
    document_profiles: tuple[str, ...]
    state: str | None = None
    production_approved: bool = False
    ca_bundle_path: Path | None = None
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        try:
            environment = (
                self.environment
                if isinstance(self.environment, RNDSEnvironment)
                else RNDSEnvironment(str(self.environment).strip().lower())
            )
        except ValueError as exc:
            raise RNDSConfigurationError("RNDS environment must be homologation or production") from exc
        object.__setattr__(self, "environment", environment)

        requester_identifier = str(self.requester_identifier).strip()
        if not _REQUESTER_IDENTIFIER.fullmatch(requester_identifier):
            raise RNDSConfigurationError("RNDS requester identifier has an invalid format")
        object.__setattr__(self, "requester_identifier", requester_identifier)

        certificate_path = self._validate_secret_file(
            self.certificate_pem_path,
            name="RNDS certificate",
        )
        private_key_path = self._validate_secret_file(
            self.private_key_pem_path,
            name="RNDS private key",
        )
        object.__setattr__(self, "certificate_pem_path", certificate_path)
        object.__setattr__(self, "private_key_pem_path", private_key_path)

        if certificate_path == private_key_path:
            raise RNDSConfigurationError("RNDS certificate and private key must use separate PEM files")

        if self.ca_bundle_path is not None:
            object.__setattr__(
                self,
                "ca_bundle_path",
                self._validate_secret_file(self.ca_bundle_path, name="RNDS CA bundle"),
            )

        profiles = tuple(
            dict.fromkeys(str(profile).strip() for profile in self.document_profiles if str(profile).strip())
        )
        if not profiles:
            raise RNDSConfigurationError("At least one institution-approved RNDS document profile is required")
        for profile in profiles:
            parsed = urlparse(profile)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise RNDSConfigurationError("RNDS document profile must be an absolute canonical URL")
        object.__setattr__(self, "document_profiles", profiles)

        timeout = float(self.timeout_seconds)
        if timeout < 1 or timeout > 60:
            raise RNDSConfigurationError("RNDS timeout must be between 1 and 60 seconds")
        object.__setattr__(self, "timeout_seconds", timeout)

        state = str(self.state or "").strip().upper() or None
        if environment is RNDSEnvironment.HOMOLOGATION:
            if state is not None:
                raise RNDSConfigurationError(
                    "RNDS homologation uses the national EHR endpoint and does not accept a state"
                )
            if self.production_approved:
                raise RNDSConfigurationError("Production approval must not be enabled in RNDS homologation")
        else:
            if not self.production_approved:
                raise RNDSConfigurationError("RNDS production requires explicit institutional approval")
            if state not in _BRAZILIAN_STATES:
                raise RNDSConfigurationError("RNDS production requires a valid Brazilian state")
        object.__setattr__(self, "state", state)

    @classmethod
    def from_environment(cls) -> "RNDSSettings":
        environment_value = os.getenv("REDISUS_RNDS_ENVIRONMENT", RNDSEnvironment.HOMOLOGATION.value)
        try:
            environment = RNDSEnvironment(environment_value.strip().lower())
        except ValueError as exc:
            raise RNDSConfigurationError("REDISUS_RNDS_ENVIRONMENT must be 'homologation' or 'production'") from exc

        required = {
            "REDISUS_RNDS_REQUESTER_ID": os.getenv("REDISUS_RNDS_REQUESTER_ID"),
            "REDISUS_RNDS_CERTIFICATE_PEM_PATH": os.getenv("REDISUS_RNDS_CERTIFICATE_PEM_PATH"),
            "REDISUS_RNDS_PRIVATE_KEY_PEM_PATH": os.getenv("REDISUS_RNDS_PRIVATE_KEY_PEM_PATH"),
            "REDISUS_RNDS_DOCUMENT_PROFILES": os.getenv("REDISUS_RNDS_DOCUMENT_PROFILES"),
        }
        missing = [name for name, value in required.items() if not str(value or "").strip()]
        if missing:
            raise RNDSConfigurationError(f"Missing RNDS configuration: {', '.join(missing)}")

        timeout_raw = os.getenv("REDISUS_RNDS_TIMEOUT_SECONDS", "30")
        try:
            timeout = float(timeout_raw)
        except ValueError as exc:
            raise RNDSConfigurationError("REDISUS_RNDS_TIMEOUT_SECONDS must be numeric") from exc

        ca_bundle = os.getenv("REDISUS_RNDS_CA_BUNDLE_PATH")
        return cls(
            environment=environment,
            requester_identifier=str(required["REDISUS_RNDS_REQUESTER_ID"]),
            certificate_pem_path=Path(str(required["REDISUS_RNDS_CERTIFICATE_PEM_PATH"])),
            private_key_pem_path=Path(str(required["REDISUS_RNDS_PRIVATE_KEY_PEM_PATH"])),
            document_profiles=tuple(
                profile.strip()
                for profile in str(required["REDISUS_RNDS_DOCUMENT_PROFILES"]).split(",")
                if profile.strip()
            ),
            state=os.getenv("REDISUS_RNDS_STATE"),
            production_approved=_environment_flag("REDISUS_RNDS_PRODUCTION_APPROVED"),
            ca_bundle_path=Path(ca_bundle) if ca_bundle else None,
            timeout_seconds=timeout,
        )

    @property
    def auth_base_url(self) -> str:
        if self.environment is RNDSEnvironment.PRODUCTION:
            return "https://ehr-auth.saude.gov.br"
        return "https://ehr-auth-hmg.saude.gov.br"

    @property
    def ehr_base_url(self) -> str:
        if self.environment is RNDSEnvironment.PRODUCTION:
            return f"https://{str(self.state).lower()}-ehr-services.saude.gov.br"
        return "https://ehr-services.hmg.saude.gov.br"

    @property
    def token_url(self) -> str:
        return f"{self.auth_base_url}/api/token"

    @property
    def fhir_base_url(self) -> str:
        return f"{self.ehr_base_url}/api/fhir/r4"

    @property
    def bundle_url(self) -> str:
        return f"{self.fhir_base_url}/Bundle"

    @property
    def bundle_identifier_system(self) -> str:
        return f"http://www.saude.gov.br/fhir/r4/NamingSystem/BRRNDS-{self.requester_identifier}"

    @property
    def client_certificate(self) -> tuple[str, str]:
        return str(self.certificate_pem_path), str(self.private_key_pem_path)

    @property
    def tls_verify(self) -> bool | str:
        return str(self.ca_bundle_path) if self.ca_bundle_path else True

    @staticmethod
    def _validate_secret_file(value: Path, *, name: str) -> Path:
        path = Path(value)
        if not path.is_absolute():
            raise RNDSConfigurationError(f"{name} path must be absolute")
        resolved = path.resolve()
        if not resolved.is_file():
            raise RNDSConfigurationError(f"{name} file was not found")
        return resolved


def _environment_flag(name: str) -> bool:
    value = str(os.getenv(name, "")).strip().lower()
    if value in {"", "0", "false", "no"}:
        return False
    if value in {"1", "true", "yes"}:
        return True
    raise RNDSConfigurationError(f"{name} must be true or false")
