from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import requests

from .config import RNDSSettings
from .exceptions import RNDSAuthenticationError


@dataclass(frozen=True, slots=True)
class RNDSToken:
    value: str
    expires_at: float


class RNDSTokenProvider:
    def __init__(
        self,
        settings: RNDSSettings,
        *,
        session: requests.Session | None = None,
        monotonic: Callable[[], float] | None = None,
        refresh_skew_seconds: float = 30.0,
    ):
        self.settings = settings
        self.session = session or requests.Session()
        self.monotonic = monotonic or time.monotonic
        self.refresh_skew_seconds = max(0.0, float(refresh_skew_seconds))
        self._cached_token: RNDSToken | None = None
        self._lock = threading.RLock()

    def access_token(self, *, force_refresh: bool = False) -> str:
        with self._lock:
            now = self.monotonic()
            if not force_refresh and self._cached_token is not None:
                remaining = self._cached_token.expires_at - now
                if remaining > self.refresh_skew_seconds:
                    return self._cached_token.value

            token, duration_seconds = self._fetch_token()
            self._cached_token = RNDSToken(
                value=token,
                expires_at=self.monotonic() + duration_seconds,
            )
            return token

    def invalidate(self) -> None:
        with self._lock:
            self._cached_token = None

    def _fetch_token(self) -> tuple[str, float]:
        try:
            response = self.session.get(
                self.settings.token_url,
                headers={"Accept": "application/json"},
                cert=self.settings.client_certificate,
                verify=self.settings.tls_verify,
                timeout=self.settings.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise RNDSAuthenticationError("RNDS authentication request failed") from exc

        if response.status_code != 200:
            raise RNDSAuthenticationError(f"RNDS authentication was rejected with HTTP {response.status_code}")

        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise RNDSAuthenticationError("RNDS authentication returned an invalid response") from exc
        if not isinstance(payload, Mapping):
            raise RNDSAuthenticationError("RNDS authentication returned an invalid response")

        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise RNDSAuthenticationError("RNDS authentication did not return an access token")

        duration_seconds = _normalize_expiration_seconds(payload.get("expires_in"))
        return token, duration_seconds


def _normalize_expiration_seconds(value: Any) -> float:
    try:
        duration = float(value)
    except (TypeError, ValueError) as exc:
        raise RNDSAuthenticationError("RNDS authentication returned an invalid token expiration") from exc

    # The RNDS guide documents expires_in=1800000 (milliseconds). Keep support
    # for conventional OAuth-style seconds without assuming one unit forever.
    if duration > 86_400:
        duration /= 1000
    if duration < 30 or duration > 86_400:
        raise RNDSAuthenticationError("RNDS authentication returned an invalid token expiration")
    return duration
