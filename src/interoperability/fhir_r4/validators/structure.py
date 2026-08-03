from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import urlparse
from uuid import UUID

from ..models import LOINC_SYSTEM, REDISUS_CODE_SYSTEM, UCUM_SYSTEM

FHIR_WOUND_CONTRACT_VERSION = "2026-08-03"

APPROVED_WOUND_LOINC_CODES = frozenset({
    "39135-9",  # Wound assessment panel
    "39127-6",  # Depth of wound
    "89260-4",  # Area of wound
    "72514-3",  # Pain severity - 0-10 verbal numeric rating
})
APPROVED_WOUND_UCUM_CODES = frozenset({"%", "1", "cm", "cm2", "cm3", "mm"})

REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "Patient": ("resourceType", "id", "name"),
    "Organization": ("resourceType", "id", "name"),
    "Practitioner": ("resourceType", "id", "name"),
    "PractitionerRole": ("resourceType", "id"),
    "Encounter": ("resourceType", "id", "status", "class", "subject"),
    "Media": ("resourceType", "id", "status", "content", "subject"),
    "Provenance": ("resourceType", "id", "target", "recorded", "agent"),
    "Observation": ("resourceType", "id", "status", "code", "subject"),
    "Condition": ("resourceType", "id", "clinicalStatus", "verificationStatus", "code", "subject"),
    "DiagnosticReport": ("resourceType", "id", "status", "code", "subject"),
    "CarePlan": ("resourceType", "id", "status", "intent", "subject"),
    "Bundle": ("resourceType", "type", "entry"),
}


class FHIRValidationError(ValueError):
    pass


def _require_mapping(resource: Mapping[str, Any] | Any) -> Mapping[str, Any]:
    if not isinstance(resource, Mapping):
        raise FHIRValidationError("FHIR payload must be a mapping")
    return resource


def validate_resource_structure(resource: Mapping[str, Any] | Any) -> list[str]:
    payload = _require_mapping(resource)
    resource_type = str(payload.get("resourceType") or "").strip()
    if not resource_type:
        return ["resourceType is required"]

    errors: list[str] = []
    for field_name in REQUIRED_FIELDS.get(resource_type, ("resourceType",)):
        value = payload.get(field_name)
        if value is None or value == "" or value == [] or value == {}:
            errors.append(f"{resource_type}.{field_name} is required")

    if resource_type in {"Patient", "Practitioner"}:
        name = payload.get("name") or []
        if not isinstance(name, list):
            errors.append(f"{resource_type}.name must be a list")

    if resource_type == "Organization":
        name = str(payload.get("name") or "").strip()
        if not name:
            errors.append("Organization.name is required")

    if resource_type in {"Observation", "Condition", "DiagnosticReport", "CarePlan", "Encounter", "Media"}:
        subject = payload.get("subject") or {}
        if not isinstance(subject, Mapping) or not str(subject.get("reference") or "").strip():
            errors.append(f"{resource_type}.subject.reference is required")

    if resource_type == "PractitionerRole":
        practitioner = payload.get("practitioner")
        organization = payload.get("organization")
        if not practitioner and not organization:
            errors.append("PractitionerRole.practitioner or PractitionerRole.organization is required")

    if resource_type == "Media":
        content = payload.get("content") or {}
        if not isinstance(content, Mapping):
            errors.append("Media.content must be a mapping")
        elif not (
            str(content.get("url") or "").strip()
            or str(content.get("data") or "").strip()
            or str(content.get("title") or "").strip()
        ):
            errors.append("Media.content must include url, data, or title")

    if resource_type == "Provenance":
        target = payload.get("target") or []
        if not isinstance(target, list) or not target:
            errors.append("Provenance.target must be a non-empty list")
        agent = payload.get("agent") or []
        if not isinstance(agent, list) or not agent:
            errors.append("Provenance.agent must be a non-empty list")

    if resource_type == "Encounter":
        class_payload = payload.get("class") or {}
        if not isinstance(class_payload, Mapping) or not str(class_payload.get("code") or "").strip():
            errors.append("Encounter.class.code is required")

    if resource_type == "Bundle":
        entry = payload.get("entry") or []
        if not isinstance(entry, list) or not entry:
            errors.append("Bundle.entry must be a non-empty list")
        for index, item in enumerate(entry):
            if not isinstance(item, Mapping):
                errors.append(f"Bundle.entry[{index}] must be a mapping")
                continue
            if "resource" not in item:
                errors.append(f"Bundle.entry[{index}].resource is required")

    return errors


def validate_with_fhir_models(resource: Mapping[str, Any] | Any) -> list[str]:
    payload = _require_mapping(resource)
    resource_type = str(payload.get("resourceType") or "").strip()
    if not resource_type:
        return ["resourceType is required"]

    model_map = {
        "Patient": ("fhir.resources.patient", "Patient"),
        "Organization": ("fhir.resources.organization", "Organization"),
        "Practitioner": ("fhir.resources.practitioner", "Practitioner"),
        "PractitionerRole": ("fhir.resources.practitionerrole", "PractitionerRole"),
        "Encounter": ("fhir.resources.encounter", "Encounter"),
        "Media": ("fhir.resources.media", "Media"),
        "Provenance": ("fhir.resources.provenance", "Provenance"),
        "Observation": ("fhir.resources.observation", "Observation"),
        "Condition": ("fhir.resources.condition", "Condition"),
        "DiagnosticReport": ("fhir.resources.diagnosticreport", "DiagnosticReport"),
        "CarePlan": ("fhir.resources.careplan", "CarePlan"),
        "Bundle": ("fhir.resources.bundle", "Bundle"),
    }
    module_info = model_map.get(resource_type)
    if not module_info:
        return []

    try:
        module = __import__(module_info[0], fromlist=[module_info[1]])
        model_class = getattr(module, module_info[1])
        model_class.model_validate(dict(payload))
        return []
    except ModuleNotFoundError:
        return []
    except Exception as exc:  # pragma: no cover - depends on optional library internals
        return [str(exc)]


def validate_resource(resource: Mapping[str, Any] | Any, strict: bool = True) -> None:
    errors = validate_resource_structure(resource)
    if strict:
        errors.extend(validate_with_fhir_models(resource))
    if errors:
        raise FHIRValidationError("; ".join(errors))


def validate_bundle(bundle: Mapping[str, Any] | Any, strict: bool = True) -> None:
    validate_resource(bundle, strict=strict)
    payload = _require_mapping(bundle)
    entries = payload.get("entry") or []
    for item in entries:
        validate_resource(item.get("resource"), strict=strict)
    # A document Bundle (for example an institution-approved RNDS document)
    # follows its target profile's contract. The REDISUS wound contract below
    # governs the collection/transaction bundles produced by this mapper.
    if str(payload.get("type") or "") != "document":
        contract_errors = validate_wound_bundle_contract(payload)
        if contract_errors:
            raise FHIRValidationError("; ".join(contract_errors))


def _walk(value: Any):
    if isinstance(value, Mapping):
        yield value
        for nested in value.values():
            yield from _walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk(nested)


def _is_absolute_url(value: str) -> bool:
    parsed = urlparse(value)
    return bool(parsed.scheme and parsed.netloc)


def validate_wound_bundle_contract(bundle: Mapping[str, Any] | Any) -> list[str]:
    """Validate the versioned REDISUS wound bundle contract without external terminology calls."""

    payload = _require_mapping(bundle)
    errors: list[str] = []
    entries = payload.get("entry") or []
    bundle_type = str(payload.get("type") or "")
    identities: set[str] = set()
    full_urls: set[str] = set()

    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            continue
        resource = entry.get("resource")
        if not isinstance(resource, Mapping):
            continue
        resource_type = str(resource.get("resourceType") or "").strip()
        resource_id = str(resource.get("id") or "").strip()
        identity = f"{resource_type}/{resource_id}" if resource_type and resource_id else ""
        if not identity:
            errors.append(f"Bundle.entry[{index}] resourceType/id is required")
        elif identity in identities:
            errors.append(f"duplicate resource identity: {identity}")
        else:
            identities.add(identity)

        full_url = str(entry.get("fullUrl") or "").strip()
        if not full_url:
            errors.append(f"Bundle.entry[{index}].fullUrl is required by contract {FHIR_WOUND_CONTRACT_VERSION}")
        elif full_url in full_urls:
            errors.append(f"duplicate Bundle.entry.fullUrl: {full_url}")
        else:
            full_urls.add(full_url)
            if full_url.startswith("urn:uuid:"):
                try:
                    UUID(full_url.removeprefix("urn:uuid:"))
                except ValueError:
                    errors.append(f"Bundle.entry[{index}].fullUrl must contain a valid UUID URN")
            elif not _is_absolute_url(full_url):
                errors.append(f"Bundle.entry[{index}].fullUrl must be an absolute URL or UUID URN")
            elif identity and not full_url.rstrip("/").endswith(identity):
                errors.append(f"Bundle.entry[{index}].fullUrl does not identify {identity}")

        request_payload = entry.get("request")
        if bundle_type == "transaction":
            if not isinstance(request_payload, Mapping):
                errors.append(f"Bundle.entry[{index}].request is required for a transaction")
            elif not request_payload.get("method") or not request_payload.get("url"):
                errors.append(f"Bundle.entry[{index}].request.method/url is required")
        elif request_payload:
            errors.append(f"Bundle.entry[{index}].request is allowed only for a transaction")

    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping) or not isinstance(entry.get("resource"), Mapping):
            continue
        for node in _walk(entry["resource"]):
            reference = str(node.get("reference") or "").strip()
            if reference and not reference.startswith("#"):
                if reference.startswith("urn:"):
                    if reference not in full_urls:
                        errors.append(f"unresolvable reference in Bundle.entry[{index}]: {reference}")
                elif not _is_absolute_url(reference) and reference not in identities:
                    errors.append(f"unresolvable reference in Bundle.entry[{index}]: {reference}")

            system = str(node.get("system") or "").strip()
            code = str(node.get("code") or "").strip()
            if system == LOINC_SYSTEM and code not in APPROVED_WOUND_LOINC_CODES:
                errors.append(
                    f"unapproved LOINC code in wound contract {FHIR_WOUND_CONTRACT_VERSION}: {code or '<empty>'}"
                )
            if system == UCUM_SYSTEM:
                if code not in APPROVED_WOUND_UCUM_CODES:
                    errors.append(f"unsupported UCUM code: {code or '<empty>'}")
                if not node.get("unit"):
                    errors.append(f"UCUM quantity {code or '<empty>'} must include unit")
            elif (node.get("unit") or node.get("code")) and "value" in node and system != UCUM_SYSTEM:
                errors.append("coded quantities must use the UCUM system")
            if system.startswith(f"{REDISUS_CODE_SYSTEM}/") and "code" in node and not code:
                errors.append(f"local REDISUS coding is missing code in Bundle.entry[{index}]")

    return errors
