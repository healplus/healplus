"""Validate versioned evidence for a Heal+ moderated usability study."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STUDY_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,127}$")
ALLOWED_STATUSES = {"pilot-rehearsal-complete", "moderated-sessions-complete"}
ALLOWED_CATEGORIES = {"usability", "safety"}
ALLOWED_SEVERITIES = {"P0", "P1", "P2", "P3"}
REQUIRED_TASK_METRICS = {"completion", "time_seconds", "errors", "assistance"}
REQUIRED_ACCESSIBILITY_CHECKS = {
    "keyboard",
    "screen_reader",
    "plain_language",
    "reduced_motion",
}
PROHIBITED_IDENTITY_KEYS = {
    "name",
    "email",
    "phone",
    "license_number",
    "registration_number",
    "patient_id",
    "recording_url",
    "transcript",
}


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


def _resolve_reference(reference: Any, project_root: Path) -> tuple[Path | None, str | None]:
    if not _nonempty_string(reference):
        return None, "must be a non-empty repository-relative path"
    if "://" in str(reference):
        return None, "must be a local repository path"
    candidate = (project_root / str(reference)).resolve()
    try:
        candidate.relative_to(project_root.resolve())
    except ValueError:
        return None, "escapes the repository"
    if not candidate.is_file():
        return candidate, "does not exist"
    return candidate, None


def _find_prohibited_keys(value: Any, *, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            if key_text.lower() in PROHIBITED_IDENTITY_KEYS:
                errors.append(f"{path}.{key_text} is prohibited in versioned usability evidence")
            errors.extend(_find_prohibited_keys(nested, path=f"{path}.{key_text}"))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            errors.extend(_find_prohibited_keys(nested, path=f"{path}[{index}]"))
    return errors


def validate_evidence(
    evidence: dict[str, Any],
    *,
    project_root: Path = PROJECT_ROOT,
) -> list[str]:
    errors = _find_prohibited_keys(evidence)

    if evidence.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    study_id = evidence.get("study_id")
    if not _nonempty_string(study_id) or not STUDY_ID_PATTERN.fullmatch(str(study_id)):
        errors.append("study_id must use lowercase letters, digits, and hyphens")

    status = evidence.get("status")
    if status not in ALLOWED_STATUSES:
        errors.append("status must be pilot-rehearsal-complete or moderated-sessions-complete")
    if not _valid_timestamp(evidence.get("executed_at")):
        errors.append("executed_at must be an ISO-8601 timestamp with timezone")

    references = evidence.get("references")
    if not isinstance(references, dict):
        errors.append("references must be an object")
        references = {}
    for field in ("protocol", "synthetic_case", "report", "backlog"):
        _, reference_error = _resolve_reference(references.get(field), project_root)
        if reference_error:
            errors.append(f"references.{field} {reference_error}")

    data_policy = evidence.get("data_policy")
    if not isinstance(data_policy, dict):
        errors.append("data_policy must be an object")
        data_policy = {}
    if data_policy.get("classification") != "synthetic-only":
        errors.append("data_policy.classification must be synthetic-only")
    if data_policy.get("real_patient_data") is not False:
        errors.append("data_policy.real_patient_data must be false")
    if data_policy.get("stores_participant_identity") is not False:
        errors.append("data_policy.stores_participant_identity must be false")
    if data_policy.get("recording_enabled") is not False:
        errors.append("data_policy.recording_enabled must be false")

    target = evidence.get("participant_target")
    if not isinstance(target, dict):
        errors.append("participant_target must be an object")
        target = {}
    minimum = target.get("minimum")
    maximum = target.get("maximum")
    live_sessions = target.get("live_sessions_completed")
    if not isinstance(minimum, int) or minimum < 1:
        errors.append("participant_target.minimum must be a positive integer")
    if not isinstance(maximum, int) or not isinstance(minimum, int) or maximum < minimum:
        errors.append("participant_target.maximum must be an integer not lower than minimum")
    if not isinstance(live_sessions, int) or live_sessions < 0:
        errors.append("participant_target.live_sessions_completed must be a non-negative integer")
    profiles = target.get("profiles")
    if not isinstance(profiles, list) or len(profiles) < 2 or not all(
        _nonempty_string(item) for item in profiles
    ):
        errors.append("participant_target.profiles must contain at least two profiles")
    if (
        status == "moderated-sessions-complete"
        and isinstance(minimum, int)
        and isinstance(live_sessions, int)
        and live_sessions < minimum
    ):
        errors.append("moderated-sessions-complete requires the minimum live session count")

    consent = evidence.get("consent")
    if not isinstance(consent, dict):
        errors.append("consent must be an object")
        consent = {}
    for field in (
        "template_in_protocol",
        "withdrawal_supported",
        "external_provider_consent_is_separate",
    ):
        if consent.get(field) is not True:
            errors.append(f"consent.{field} must be true")
    if consent.get("stores_identity") is not False:
        errors.append("consent.stores_identity must be false")

    tasks = evidence.get("tasks")
    task_ids: list[str] = []
    if not isinstance(tasks, list) or len(tasks) < 6:
        errors.append("tasks must contain the six golden-path tasks")
        tasks = []
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            errors.append(f"tasks[{index}] must be an object")
            continue
        task_id = task.get("id")
        if not _nonempty_string(task_id):
            errors.append(f"tasks[{index}].id is required")
        else:
            task_ids.append(str(task_id))
        for field in ("title", "success_criteria", "safety_stop"):
            if not _nonempty_string(task.get(field)):
                errors.append(f"tasks[{index}].{field} is required")
        metrics = task.get("metrics")
        if not isinstance(metrics, list) or not REQUIRED_TASK_METRICS.issubset(set(metrics)):
            errors.append(f"tasks[{index}].metrics is missing required metrics")
    if len(task_ids) != len(set(task_ids)):
        errors.append("task ids must be unique")

    accessibility = evidence.get("accessibility_review")
    if not isinstance(accessibility, dict):
        errors.append("accessibility_review must be an object")
        accessibility = {}
    if accessibility.get("status") != "completed":
        errors.append("accessibility_review.status must be completed")
    _, accessibility_error = _resolve_reference(accessibility.get("evidence"), project_root)
    if accessibility_error:
        errors.append(f"accessibility_review.evidence {accessibility_error}")
    checks = accessibility.get("checks")
    if not isinstance(checks, list) or not REQUIRED_ACCESSIBILITY_CHECKS.issubset(set(checks)):
        errors.append("accessibility_review.checks is incomplete")

    findings = evidence.get("findings")
    finding_ids: list[str] = []
    categories: set[str] = set()
    if not isinstance(findings, list) or not findings:
        errors.append("findings must contain at least one finding")
        findings = []
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            errors.append(f"findings[{index}] must be an object")
            continue
        finding_id = finding.get("id")
        if not _nonempty_string(finding_id):
            errors.append(f"findings[{index}].id is required")
        else:
            finding_ids.append(str(finding_id))
        category = finding.get("category")
        if category not in ALLOWED_CATEGORIES:
            errors.append(f"findings[{index}].category must be usability or safety")
        else:
            categories.add(str(category))
        severity = finding.get("severity")
        if severity not in ALLOWED_SEVERITIES:
            errors.append(f"findings[{index}].severity is invalid")
        for field in ("title", "evidence"):
            if not _nonempty_string(finding.get(field)):
                errors.append(f"findings[{index}].{field} is required")
        if severity in {"P0", "P1"}:
            action = finding.get("action")
            if not isinstance(action, dict):
                errors.append(f"findings[{index}].action is required for P0/P1")
                continue
            issue = action.get("issue")
            if not _nonempty_string(issue) or not str(issue).startswith(
                "https://github.com/healplus/healplus/issues/"
            ):
                errors.append(f"findings[{index}].action.issue must reference a Heal+ issue")
            if not _nonempty_string(action.get("owner_role")):
                errors.append(f"findings[{index}].action.owner_role is required")
            if action.get("status") not in {"open", "in-progress", "closed"}:
                errors.append(f"findings[{index}].action.status is invalid")
    if len(finding_ids) != len(set(finding_ids)):
        errors.append("finding ids must be unique")
    if categories != ALLOWED_CATEGORIES:
        errors.append("findings must separate usability and safety categories")

    limitations = evidence.get("limitations")
    if not isinstance(limitations, list) or not limitations or not all(
        _nonempty_string(item) for item in limitations
    ):
        errors.append("limitations must contain explicit non-empty statements")

    return errors


def load_evidence(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("evidence root must be an object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()

    evidence_path = args.evidence.resolve()
    try:
        evidence_path.relative_to(PROJECT_ROOT)
    except ValueError:
        print("ERROR: evidence path must stay inside the repository")
        return 1

    try:
        evidence = load_evidence(evidence_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read usability evidence: {exc}")
        return 1

    errors = validate_evidence(evidence)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(
        "Usability evidence valid: "
        f"study={evidence['study_id']} status={evidence['status']} "
        f"live_sessions={evidence['participant_target']['live_sessions_completed']} "
        f"findings={len(evidence['findings'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

