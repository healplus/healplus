"""Supabase HTTP boundary: every data request uses the caller's JWT and RLS."""

from __future__ import annotations

import os
from urllib.parse import quote, urlparse

import requests
from flask import request


class SupabaseUnavailable(RuntimeError):
    """Safe error without upstream bodies, credentials, or clinical data."""


def configuration() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")).strip()
    parsed = urlparse(url)
    if not key or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SupabaseUnavailable("Supabase configuration unavailable")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}):
        raise SupabaseUnavailable("Supabase requires HTTPS")
    return url, key


def is_supabase_ready() -> bool:
    try:
        configuration()
        return True
    except SupabaseUnavailable:
        return False


class SupabaseClient:
    def __init__(self, token: str):
        self.url, key = configuration()
        self.headers = {"apikey": key, "Authorization": f"Bearer {token}"}

    def call(self, method: str, path: str, **kwargs):
        headers = {**self.headers, **kwargs.pop("headers", {})}
        try:
            response = requests.request(
                method, f"{self.url}{path}", headers=headers, timeout=(5, 20),
                allow_redirects=False, **kwargs,
            )
            if not 200 <= response.status_code < 300:
                raise SupabaseUnavailable("Supabase request failed")
            return response.json() if response.content else None
        except (requests.RequestException, ValueError):
            raise SupabaseUnavailable("Supabase request failed") from None

    def select(self, table: str, **params):
        return self.call("GET", f"/rest/v1/{table}", params=params) or []

    def rpc(self, name: str, payload: dict):
        return self.call("POST", f"/rest/v1/rpc/{name}", json=payload)

    def insert(self, table: str, payload: dict):
        return self.call("POST", f"/rest/v1/{table}", json=payload)

    def upload(self, path: str, content: bytes, mime: str):
        self.call("POST", f"/storage/v1/object/analysis-images/{quote(path, safe='/')}",
                  data=content, headers={"Content-Type": mime, "x-upsert": "false"})


def request_client() -> SupabaseClient:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer ") or not header[7:].strip():
        raise SupabaseUnavailable("Supabase authentication required")
    return SupabaseClient(header[7:].strip())


class SupabaseAuth:
    def verify_id_token(self, token: str, *, check_revoked: bool = True) -> dict:
        client = SupabaseClient(token)
        user = client.call("GET", "/auth/v1/user")
        if not isinstance(user, dict) or not user.get("id"):
            raise SupabaseUnavailable("Invalid authentication token")
        if check_revoked and client.rpc("current_session_is_active", {}) is not True:
            raise SupabaseUnavailable("Inactive authentication session")
        # Only server-controlled metadata can grant clinical roles or scope.
        metadata = user.get("app_metadata") or {}
        allowed = ("roles", "role", "redisus_roles", "redisus_role", "patient_ids", "unit_ids", "unit_id", "allowed_unit_ids")
        return {**{key: metadata[key] for key in allowed if key in metadata},
                "uid": user["id"], "sub": user["id"], "email": user.get("email", "")}

    def revoke_refresh_tokens(self, uid: str) -> None:
        # The authenticated caller can revoke only their own sessions.
        client = request_client()
        user = client.call("GET", "/auth/v1/user")
        if user.get("id") != uid:
            raise SupabaseUnavailable("Session owner mismatch")
        client.call("POST", "/auth/v1/logout", params={"scope": "global"})
