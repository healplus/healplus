"""Minimal append-only audit contract for clinical and security events."""

from __future__ import annotations

import re
from math import isfinite
from datetime import datetime, timezone
from typing import Any, Mapping


class AuditContractError(ValueError):
    """Raised when an event would violate the minimal audit contract."""


AUDIT_CONTRACT_VERSION = "1.0"
AUDIT_OUTCOMES = frozenset({"denied", "failed", "succeeded"})
AUDIT_ACTOR_TYPES = frozenset({"human", "system"})
AUDIT_METADATA_ALLOWLIST = frozenset(
    {
        "attempts",
        "bundle_hash",
        "consent_scope",
        "degraded",
        "http_status",
        "mode",
        "model",
        "provider",
        "publication_id",
        "reason_code",
        "review_required",
        "run_id",
        "severity",
        "source",
        "status",
        "target_role",
    }
)

_ACTION_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,79}$")
_FORBIDDEN_KEY_PARTS = (
    "after",
    "api_key",
    "before",
    "clinical",
    "content",
    "credential",
    "email",
    "image",
    "medical_record",
    "name",
    "note",
    "patient",
    "phone",
    "prompt",
    "secret",
    "token",
)


def _required_text(value: Any, field: str, *, max_length: int = 180) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise AuditContractError(f"{field} is required")
    if len(normalized) > max_length:
        raise AuditContractError(f"{field} exceeds {max_length} characters")
    return normalized


def normalize_audit_metadata(
    metadata: Mapping[str, Any] | None,
    *,
    strict: bool = True,
) -> dict[str, str | int | float | bool]:
    """Keep only explicitly safe scalar metadata.

    Strict mode is used at trust boundaries and rejects unknown or sensitive
    fields. Compatibility callers may use non-strict mode to drop legacy data.
    """

    normalized: dict[str, str | int | float | bool] = {}
    for raw_key, value in dict(metadata or {}).items():
        key = str(raw_key).strip().lower()
        forbidden = any(part in key for part in _FORBIDDEN_KEY_PARTS)
        if forbidden or key not in AUDIT_METADATA_ALLOWLIST:
            if strict:
                raise AuditContractError(f"metadata field is not allowed: {key}")
            continue
        if not isinstance(value, (str, int, float, bool)) or isinstance(value, bytes):
            if strict:
                raise AuditContractError(f"metadata value must be scalar: {key}")
            continue
        if isinstance(value, float) and not isfinite(value):
            if strict:
                raise AuditContractError(f"metadata value must be finite: {key}")
            continue
        if isinstance(value, str):
            value = value.strip()[:180]
        normalized[key] = value
    return normalized


def build_audit_event(
    payload: Mapping[str, Any],
    *,
    strict_metadata: bool = True,
) -> dict[str, Any]:
    action = _required_text(payload.get("action"), "action", max_length=80)
    if not _ACTION_PATTERN.fullmatch(action):
        raise AuditContractError("action must use lowercase snake_case")

    actor_type = str(payload.get("actor_type") or "human").strip().lower()
    if actor_type not in AUDIT_ACTOR_TYPES:
        raise AuditContractError("actor_type must be human or system")

    outcome = str(payload.get("outcome") or "succeeded").strip().lower()
    if outcome not in AUDIT_OUTCOMES:
        raise AuditContractError("outcome must be succeeded, denied, or failed")

    created_at = str(payload.get("created_at") or datetime.now(timezone.utc).isoformat()).strip()
    try:
        parsed_created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuditContractError("created_at must be an RFC 3339 date-time") from exc
    if parsed_created_at.tzinfo is None:
        raise AuditContractError("created_at must include a timezone")
    return {
        "contract_version": AUDIT_CONTRACT_VERSION,
        "actor_type": actor_type,
        "actor_id": _required_text(payload.get("actor_id"), "actor_id"),
        "actor_role": _required_text(payload.get("actor_role") or "unknown", "actor_role", max_length=80),
        "action": action,
        "target_type": _required_text(payload.get("target_type"), "target_type", max_length=80),
        "target_id": _required_text(payload.get("target_id"), "target_id"),
        "patient_id": _required_text(payload.get("patient_id"), "patient_id")
        if str(payload.get("patient_id") or "").strip()
        else None,
        "case_id": _required_text(payload.get("case_id"), "case_id")
        if str(payload.get("case_id") or "").strip()
        else None,
        "request_id": _required_text(payload.get("request_id"), "request_id"),
        "outcome": outcome,
        "metadata": normalize_audit_metadata(payload.get("metadata"), strict=strict_metadata),
        "created_at": created_at,
    }
