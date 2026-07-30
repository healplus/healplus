from __future__ import annotations

from typing import Any, Mapping

from .config import RNDSSettings
from .exceptions import RNDSBundleValidationError


def validate_rnds_document_bundle(bundle: Mapping[str, Any], settings: RNDSSettings) -> None:
    if bundle.get("resourceType") != "Bundle":
        raise RNDSBundleValidationError("RNDS submission requires a FHIR Bundle")
    if bundle.get("type") != "document":
        raise RNDSBundleValidationError("RNDS submission requires Bundle.type=document")

    identifier = bundle.get("identifier")
    if not isinstance(identifier, Mapping):
        raise RNDSBundleValidationError("RNDS Bundle.identifier is required")
    if str(identifier.get("system") or "").strip() != settings.bundle_identifier_system:
        raise RNDSBundleValidationError("RNDS Bundle.identifier.system does not match the accredited requester")
    identifier_value = str(identifier.get("value") or "").strip()
    if not identifier_value or len(identifier_value) > 160:
        raise RNDSBundleValidationError("RNDS Bundle.identifier.value must be a stable local identifier")

    entries = bundle.get("entry")
    if not isinstance(entries, list) or not entries:
        raise RNDSBundleValidationError("RNDS document Bundle must contain entries")
    first_entry = entries[0]
    if not isinstance(first_entry, Mapping):
        raise RNDSBundleValidationError("RNDS document Bundle first entry is invalid")
    composition = first_entry.get("resource")
    if not isinstance(composition, Mapping) or composition.get("resourceType") != "Composition":
        raise RNDSBundleValidationError("RNDS document Bundle first entry must be a Composition")
    if composition.get("status") != "final":
        raise RNDSBundleValidationError("RNDS Composition.status must be final")

    meta = composition.get("meta")
    profiles = meta.get("profile") if isinstance(meta, Mapping) else None
    if not isinstance(profiles, list) or not any(
        str(profile).strip() in settings.document_profiles for profile in profiles
    ):
        raise RNDSBundleValidationError("RNDS Composition must declare an institution-approved document profile")
