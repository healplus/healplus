"""Validate a versioned Heal+ pilot release evidence manifest."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{7,40}$")
ALLOWED_DECISIONS = {"GO", "NO-GO"}
ALLOWED_RISKS = {"P0", "P1", "P2"}
ALLOWED_GATE_STATUSES = {"pass", "blocked", "fail", "not-applicable"}
ALLOWED_APPROVAL_STATUSES = {"approved", "pending", "rejected", "not-applicable"}
REQUIRED_APPROVAL_ROLES = {"clinical", "privacy", "release"}


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_timestamp(value: Any) -> bool:
    if not _nonempty_string(value):
        return False
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _resolve_reference(reference: str, project_root: Path) -> tuple[Path | None, str | None]:
    if reference.startswith("https://"):
        return None, None
    if "://" in reference:
        return None, "evidence URLs must use https://"

    path_value = reference.split("#", 1)[0]
    if not path_value:
        return None, "evidence path cannot be empty"
    candidate = (project_root / path_value).resolve()
    try:
        candidate.relative_to(project_root.resolve())
    except ValueError:
        return None, "evidence path escapes the repository"
    if not candidate.exists():
        return candidate, "evidence path does not exist"
    return candidate, None


def _validate_references(
    references: Any,
    *,
    field: str,
    project_root: Path,
    errors: list[str],
) -> list[str]:
    if not isinstance(references, list) or not references:
        errors.append(f"{field} must contain at least one evidence reference")
        return []

    valid_references: list[str] = []
    for index, reference in enumerate(references):
        if not _nonempty_string(reference):
            errors.append(f"{field}[{index}] must be a non-empty string")
            continue
        _, error = _resolve_reference(reference, project_root)
        if error:
            errors.append(f"{field}[{index}] {error}: {reference}")
            continue
        valid_references.append(reference)
    return valid_references


def validate_manifest(
    manifest: dict[str, Any],
    *,
    project_root: Path = PROJECT_ROOT,
    require_go: bool = False,
    expected_candidate: str | None = None,
    expected_release_notes: str | None = None,
) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    candidate = manifest.get("candidate")
    if not _nonempty_string(candidate) or not CANDIDATE_PATTERN.fullmatch(str(candidate)):
        errors.append("candidate must contain only letters, digits, dots, underscores, and hyphens")
    elif expected_candidate and candidate != expected_candidate:
        errors.append(f"candidate must match {expected_candidate!r}")

    commit_sha = manifest.get("commit_sha")
    if not _nonempty_string(commit_sha) or not COMMIT_PATTERN.fullmatch(str(commit_sha)):
        errors.append("commit_sha must be a 7-40 character lowercase Git SHA")

    if not _valid_timestamp(manifest.get("generated_at")):
        errors.append("generated_at must be an ISO-8601 timestamp with timezone")

    release_notes = manifest.get("release_notes")
    if not _nonempty_string(release_notes):
        errors.append("release_notes must be a repository-relative path")
        release_notes_path = None
    else:
        release_notes_path, reference_error = _resolve_reference(str(release_notes), project_root)
        if reference_error or release_notes_path is None:
            errors.append(f"release_notes {reference_error or 'must be a local repository path'}")
        if expected_release_notes and release_notes != expected_release_notes:
            errors.append(f"release_notes must match {expected_release_notes!r}")

    decision = manifest.get("decision")
    if not isinstance(decision, dict):
        errors.append("decision must be an object")
        decision = {}
    outcome = decision.get("outcome")
    if outcome not in ALLOWED_DECISIONS:
        errors.append("decision.outcome must be GO or NO-GO")
    if not _nonempty_string(decision.get("rationale")):
        errors.append("decision.rationale must be recorded")
    if not _valid_timestamp(decision.get("decided_at")):
        errors.append("decision.decided_at must be an ISO-8601 timestamp with timezone")

    approvals = decision.get("approvals")
    approval_by_role: dict[str, dict[str, Any]] = {}
    if not isinstance(approvals, list):
        errors.append("decision.approvals must be a list")
        approvals = []
    for index, approval in enumerate(approvals):
        if not isinstance(approval, dict):
            errors.append(f"decision.approvals[{index}] must be an object")
            continue
        role = approval.get("role")
        status = approval.get("status")
        if not _nonempty_string(role):
            errors.append(f"decision.approvals[{index}].role is required")
            continue
        if role in approval_by_role:
            errors.append(f"decision.approvals contains duplicate role: {role}")
        approval_by_role[str(role)] = approval
        if status not in ALLOWED_APPROVAL_STATUSES:
            errors.append(f"decision.approvals[{index}].status is invalid")
        _validate_references(
            approval.get("evidence"),
            field=f"decision.approvals[{index}].evidence",
            project_root=project_root,
            errors=errors,
        )

    missing_roles = sorted(REQUIRED_APPROVAL_ROLES - set(approval_by_role))
    if missing_roles:
        errors.append(f"decision.approvals missing required roles: {', '.join(missing_roles)}")

    limitations = manifest.get("limitations")
    limitation_ids: list[str] = []
    if not isinstance(limitations, list) or not limitations:
        errors.append("limitations must contain at least one documented limitation")
        limitations = []
    for index, limitation in enumerate(limitations):
        if not isinstance(limitation, dict):
            errors.append(f"limitations[{index}] must be an object")
            continue
        limitation_id = limitation.get("id")
        if not _nonempty_string(limitation_id):
            errors.append(f"limitations[{index}].id is required")
        else:
            limitation_ids.append(str(limitation_id))
        if not _nonempty_string(limitation.get("description")):
            errors.append(f"limitations[{index}].description is required")
    if len(limitation_ids) != len(set(limitation_ids)):
        errors.append("limitation ids must be unique")

    rollback = manifest.get("rollback")
    if not isinstance(rollback, dict):
        errors.append("rollback must be an object")
        rollback = {}
    if not _nonempty_string(rollback.get("target")):
        errors.append("rollback.target is required")
    procedure = rollback.get("procedure")
    if not _nonempty_string(procedure):
        errors.append("rollback.procedure is required")
    else:
        _, procedure_error = _resolve_reference(str(procedure), project_root)
        if procedure_error:
            errors.append(f"rollback.procedure {procedure_error}: {procedure}")

    gates = manifest.get("gates")
    gate_ids: list[str] = []
    p0_nonpassing: list[str] = []
    if not isinstance(gates, list) or not gates:
        errors.append("gates must contain at least one gate")
        gates = []
    for index, gate in enumerate(gates):
        if not isinstance(gate, dict):
            errors.append(f"gates[{index}] must be an object")
            continue
        gate_id = gate.get("id")
        risk = gate.get("risk")
        status = gate.get("status")
        if not _nonempty_string(gate_id):
            errors.append(f"gates[{index}].id is required")
            gate_id = f"index-{index}"
        else:
            gate_ids.append(str(gate_id))
        if not _nonempty_string(gate.get("title")):
            errors.append(f"gates[{index}].title is required")
        if risk not in ALLOWED_RISKS:
            errors.append(f"gates[{index}].risk is invalid")
        if status not in ALLOWED_GATE_STATUSES:
            errors.append(f"gates[{index}].status is invalid")
        if risk == "P0" and status != "pass":
            p0_nonpassing.append(str(gate_id))
        _validate_references(
            gate.get("evidence"),
            field=f"gates[{index}].evidence",
            project_root=project_root,
            errors=errors,
        )
    if len(gate_ids) != len(set(gate_ids)):
        errors.append("gate ids must be unique")

    go_requested = require_go or outcome == "GO"
    if go_requested:
        if outcome != "GO":
            errors.append("release requires decision.outcome GO")
        if p0_nonpassing:
            errors.append(f"release blocked by non-passing P0 gates: {', '.join(p0_nonpassing)}")
        pending_approvals = sorted(
            role
            for role in REQUIRED_APPROVAL_ROLES
            if approval_by_role.get(role, {}).get("status") != "approved"
        )
        if pending_approvals:
            errors.append(f"release requires approved roles: {', '.join(pending_approvals)}")
        if release_notes_path and release_notes_path.is_file():
            notes = release_notes_path.read_text(encoding="utf-8").lower()
            missing_limitations = [item for item in limitation_ids if item.lower() not in notes]
            if missing_limitations:
                errors.append(
                    "release notes must reference every limitation id: "
                    + ", ".join(missing_limitations)
                )

    return errors


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("manifest root must be an object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--require-go", action="store_true")
    parser.add_argument("--expected-candidate")
    parser.add_argument("--expected-release-notes")
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    try:
        manifest_path.relative_to(PROJECT_ROOT)
    except ValueError:
        print("ERROR: manifest path must stay inside the repository")
        return 1

    try:
        manifest = load_manifest(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read pilot gate manifest: {exc}")
        return 1

    errors = validate_manifest(
        manifest,
        require_go=args.require_go,
        expected_candidate=args.expected_candidate,
        expected_release_notes=args.expected_release_notes,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    p0_gates = [gate for gate in manifest["gates"] if gate.get("risk") == "P0"]
    p0_passed = sum(gate.get("status") == "pass" for gate in p0_gates)
    print(
        f"Pilot gate manifest valid: candidate={manifest['candidate']} "
        f"decision={manifest['decision']['outcome']} p0={p0_passed}/{len(p0_gates)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
