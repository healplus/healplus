"""Deny-by-default RBAC and transactional, tamper-evident local audit storage.

Principals and scopes must be constructed by a trusted authenticated service,
never from caller-submitted claims. This module is a policy boundary, not an
authentication server. Pseudonymized patient data is still sensitive data.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import threading
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field

from .clinical_models import StrictModel


class Role(str, Enum):
    ADMINISTRADOR = "Administrador"
    ENFERMEIRO = "Enfermeiro"
    MEDICO = "Médico"
    ESTOMATERAPEUTA = "Estomaterapeuta"
    PESQUISADOR = "Pesquisador"
    ORIENTADOR = "Orientador"
    DESENVOLVEDOR = "Desenvolvedor"
    PACIENTE = "Paciente"


class Action(str, Enum):
    READ_RECORD = "read_record"
    REGISTER_PATIENT = "register_patient"
    WRITE_RECORD = "write_record"
    UPLOAD_IMAGE = "upload_image"
    MARK_ROI = "mark_roi"
    REVIEW_CLINICAL = "review_clinical"
    RECORD_CARE_PLAN = "record_care_plan"
    GENERATE_REPORT = "generate_report"
    EXPORT = "export"
    DELETE_RECORD = "delete_record"
    MANAGE_USERS = "manage_users"
    CONFIGURE = "configure"
    VIEW_AUDIT = "view_audit"
    READ_RESEARCH = "read_research"
    RUN_EXPERIMENT = "run_experiment"
    READ_DOCUMENTATION = "read_documentation"


class DataClass(str, Enum):
    IDENTIFIABLE = "identifiable"
    DEIDENTIFIED = "deidentified"
    SYNTHETIC = "synthetic"
    PUBLIC = "public"
    METADATA = "metadata"


class Principal(StrictModel):
    user_id: UUID
    tenant_id: UUID
    role: Role
    authenticated: bool = False
    authorized_patient_ids: frozenset[UUID] = frozenset()
    own_patient_id: UUID | None = None


class ResourceScope(StrictModel):
    tenant_id: UUID
    resource_id: UUID
    data_class: DataClass
    patient_id: UUID | None = None
    research_approved: bool = False
    export_authorized: bool = False
    deletion_authorized: bool = False


class AccessPolicy(StrictModel):
    # RT-HEAL-002 reserves the patient module for a future implementation.
    patient_portal_enabled: bool = False


class AuditOutcome(str, Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    COMPLETED = "completed"
    FAILED = "failed"


class AuditReason(str, Enum):
    POLICY_ALLOWED = "policy_allowed"
    AUTHENTICATION_REQUIRED = "authentication_required"
    TENANT_MISMATCH = "tenant_mismatch"
    ROLE_NOT_ALLOWED = "role_not_allowed"
    PATIENT_LINK_REQUIRED = "patient_link_required"
    RESEARCH_APPROVAL_REQUIRED = "research_approval_required"
    EXPLICIT_AUTHORIZATION_REQUIRED = "explicit_authorization_required"
    PATIENT_PORTAL_DISABLED = "patient_portal_disabled"
    OPERATION_COMPLETED = "operation_completed"
    OPERATION_FAILED = "operation_failed"


class AuditEvent(StrictModel):
    """No free text, patient identifiers, payloads, paths, tokens or credentials."""

    event_id: UUID = Field(default_factory=uuid4)
    occurred_at: AwareDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor_id: UUID
    tenant_id: UUID
    action: Action
    outcome: AuditOutcome
    reason: AuditReason
    correlation_id: UUID
    # Opaque event correlation; do not put a patient/wound ID here.


class AccessDecision(StrictModel):
    allowed: bool
    reason: AuditReason


class AccessDenied(PermissionError):
    """Public-safe failure: it intentionally contains no resource information."""


_CLINICIANS = frozenset({Role.ENFERMEIRO, Role.MEDICO, Role.ESTOMATERAPEUTA})
_RESEARCHERS = frozenset({Role.PESQUISADOR, Role.ORIENTADOR, Role.DESENVOLVEDOR})
_CARE_ACTIONS = frozenset(
    {
        Action.READ_RECORD,
        Action.WRITE_RECORD,
        Action.UPLOAD_IMAGE,
        Action.MARK_ROI,
        Action.REVIEW_CLINICAL,
        Action.RECORD_CARE_PLAN,
        Action.GENERATE_REPORT,
        Action.EXPORT,
        Action.DELETE_RECORD,
    }
)
_RESEARCH_ACTIONS = frozenset({Action.READ_RESEARCH, Action.RUN_EXPERIMENT, Action.READ_DOCUMENTATION, Action.EXPORT})
_ADMIN_ACTIONS = frozenset({Action.MANAGE_USERS, Action.CONFIGURE, Action.VIEW_AUDIT, Action.READ_DOCUMENTATION})


def decide_access(
    principal: Principal, action: Action, resource: ResourceScope, policy: AccessPolicy | None = None
) -> AccessDecision:
    """Evaluate RN01/02/03/09/12/13/14 without disclosing sensitive details."""
    action = Action(action)
    policy = policy or AccessPolicy()

    def decision(allowed: bool, reason: AuditReason) -> AccessDecision:
        return AccessDecision(allowed=allowed, reason=reason)

    if not principal.authenticated:
        return decision(False, AuditReason.AUTHENTICATION_REQUIRED)
    if principal.tenant_id != resource.tenant_id:
        return decision(False, AuditReason.TENANT_MISMATCH)
    if action == Action.EXPORT and not resource.export_authorized:
        return decision(False, AuditReason.EXPLICIT_AUTHORIZATION_REQUIRED)
    if action == Action.DELETE_RECORD and not resource.deletion_authorized:
        return decision(False, AuditReason.EXPLICIT_AUTHORIZATION_REQUIRED)

    if principal.role == Role.ADMINISTRADOR:
        allowed = action in _ADMIN_ACTIONS and resource.data_class == DataClass.METADATA
        return decision(allowed, AuditReason.POLICY_ALLOWED if allowed else AuditReason.ROLE_NOT_ALLOWED)

    if principal.role == Role.PACIENTE:
        if not policy.patient_portal_enabled:
            return decision(False, AuditReason.PATIENT_PORTAL_DISABLED)
        own = resource.patient_id is not None and resource.patient_id == principal.own_patient_id
        allowed = own and action == Action.READ_RECORD and resource.data_class == DataClass.IDENTIFIABLE
        return decision(allowed, AuditReason.POLICY_ALLOWED if allowed else AuditReason.PATIENT_LINK_REQUIRED)

    if principal.role in _RESEARCHERS:
        if action not in _RESEARCH_ACTIONS:
            return decision(False, AuditReason.ROLE_NOT_ALLOWED)
        if resource.data_class == DataClass.DEIDENTIFIED:
            if not resource.research_approved:
                return decision(False, AuditReason.RESEARCH_APPROVAL_REQUIRED)
            # A deidentified resource must not carry a patient linkage.
            allowed = resource.patient_id is None
        else:
            allowed = resource.patient_id is None and resource.data_class in {
                DataClass.SYNTHETIC,
                DataClass.PUBLIC,
                DataClass.METADATA,
            }
        return decision(allowed, AuditReason.POLICY_ALLOWED if allowed else AuditReason.ROLE_NOT_ALLOWED)

    if principal.role in _CLINICIANS:
        if action == Action.READ_DOCUMENTATION and resource.data_class == DataClass.METADATA:
            return decision(True, AuditReason.POLICY_ALLOWED)
        if action == Action.REGISTER_PATIENT:
            allowed = principal.role == Role.ENFERMEIRO and resource.data_class == DataClass.METADATA
            return decision(allowed, AuditReason.POLICY_ALLOWED if allowed else AuditReason.ROLE_NOT_ALLOWED)
        if action not in _CARE_ACTIONS or resource.data_class != DataClass.IDENTIFIABLE:
            return decision(False, AuditReason.ROLE_NOT_ALLOWED)
        if resource.patient_id is None or resource.patient_id not in principal.authorized_patient_ids:
            return decision(False, AuditReason.PATIENT_LINK_REQUIRED)
        return decision(True, AuditReason.POLICY_ALLOWED)
    return decision(False, AuditReason.ROLE_NOT_ALLOWED)


def authorize(
    principal: Principal,
    action: Action,
    resource: ResourceScope,
    *,
    policy: AccessPolicy | None = None,
    audit: AuditStore | None = None,
    correlation_id: UUID | None = None,
) -> AccessDecision:
    """Enforce policy and optionally persist both denials and grants.

    Wire ``audit`` in application services. If persistence fails, the exception
    propagates and the operation is not authorized (fail closed).
    """
    action = Action(action)
    decision = decide_access(principal, action, resource, policy)
    if audit is not None:
        audit.append(
            AuditEvent(
                actor_id=principal.user_id,
                tenant_id=principal.tenant_id,
                action=action,
                outcome=AuditOutcome.ALLOWED if decision.allowed else AuditOutcome.DENIED,
                reason=decision.reason,
                correlation_id=correlation_id or uuid4(),
            )
        )
    if not decision.allowed:
        raise AccessDenied("Acesso não autorizado para esta operação.")
    return decision


class AuditIntegrityError(RuntimeError):
    pass


class AuditStore:
    """SQLite event journal with a keyed HMAC-SHA256 chain.

    Use a durable, separately protected 32+ byte integrity key, never committed
    to source control. SQLite serializes writers via BEGIN IMMEDIATE. Verification
    detects edited payloads, gaps/reordering and wrong keys. A trusted external
    checkpoint is needed to detect deletion of the final records or replacement
    of the entire journal; ``checkpoint()`` supplies the value to anchor outside
    this file. This is tamper evidence, not immutable storage or encryption.
    """

    def __init__(self, db_path: str | Path, integrity_key: bytes):
        if not isinstance(integrity_key, bytes) or len(integrity_key) < 32:
            raise ValueError("A chave de integridade deve conter pelo menos 32 bytes.")
        self._path = str(db_path)
        self._key = integrity_key
        self._lock = threading.RLock()
        # One persistent connection supports :memory: and avoids hidden files.
        self._connection = sqlite3.connect(self._path, timeout=10, check_same_thread=False)
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS heal_audit_events (sequence INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, previous_mac TEXT NOT NULL, mac TEXT NOT NULL)"
        )
        self._connection.commit()
        self.verify_integrity()

    @staticmethod
    def _canonical(event: AuditEvent) -> str:
        return json.dumps(event.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def _mac(self, sequence: int, payload: str, previous: str) -> str:
        message = f"{sequence}\n{previous}\n{payload}".encode("utf-8")
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def append(self, event: AuditEvent) -> None:
        with self._lock:
            self._append(event)

    def _append(self, event: AuditEvent) -> None:
        if not isinstance(event, AuditEvent):
            raise TypeError("A auditoria aceita apenas eventos estruturados.")
        connection = self._connection
        try:
            connection.execute("BEGIN IMMEDIATE")
            # Verify while holding the writer lock; do not extend a damaged log.
            self.verify_integrity()
            last = connection.execute(
                "SELECT sequence, mac FROM heal_audit_events ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            sequence, previous = (last[0] + 1, last[1]) if last else (1, "0" * 64)
            payload = self._canonical(event)
            connection.execute(
                "INSERT INTO heal_audit_events(sequence,event_id,payload,previous_mac,mac) VALUES(?,?,?,?,?)",
                (sequence, str(event.event_id), payload, previous, self._mac(sequence, payload, previous)),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def verify_integrity(self, expected_checkpoint: tuple[int, str] | None = None) -> bool:
        with self._lock:
            return self._verify_integrity(expected_checkpoint)

    def _verify_integrity(self, expected_checkpoint: tuple[int, str] | None = None) -> bool:
        previous = "0" * 64
        count = 0
        for sequence, event_id, payload, previous_mac, mac in self._connection.execute(
            "SELECT sequence,event_id,payload,previous_mac,mac FROM heal_audit_events ORDER BY sequence"
        ):
            count += 1
            if (
                sequence != count
                or previous_mac != previous
                or not hmac.compare_digest(mac, self._mac(sequence, payload, previous))
            ):
                raise AuditIntegrityError("A integridade do registro de auditoria não pôde ser confirmada.")
            try:
                event = AuditEvent.model_validate_json(payload)
            except ValueError as exc:
                raise AuditIntegrityError("Evento de auditoria inválido.") from exc
            if str(event.event_id) != event_id:
                raise AuditIntegrityError("Referência de evento de auditoria inválida.")
            previous = mac
        if expected_checkpoint is not None and (count, previous) != expected_checkpoint:
            raise AuditIntegrityError("O registro de auditoria diverge do checkpoint confiável.")
        return True

    def checkpoint(self) -> tuple[int, str]:
        with self._lock:
            self.verify_integrity()
            last = self._connection.execute(
                "SELECT sequence,mac FROM heal_audit_events ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            return (last[0], last[1]) if last else (0, "0" * 64)

    def events(self) -> tuple[AuditEvent, ...]:
        """For a trusted audit service; authorize VIEW_AUDIT before exposing it."""
        with self._lock:
            self.verify_integrity()
            return tuple(
                AuditEvent.model_validate_json(row[0])
                for row in self._connection.execute("SELECT payload FROM heal_audit_events ORDER BY sequence")
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> AuditStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
