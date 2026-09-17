# -*- coding: utf-8 -*-
"""FHIR R4 adapter building conforming Media and Observation resources with validation."""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional
import urllib.request
import json

from src.interoperability.fhir_r4.models.media import MediaResource
from src.interoperability.fhir_r4.models.observation import ObservationResource
from src.interoperability.fhir_r4.validators.structure import (
    validate_resource_structure,
    validate_with_fhir_models,
)
from .assessment import ALGORITHM_VERSION, LIMITATION


class FHIRAdapter:
    """Constructs and validates FHIR R4 resources for image quality and storage."""

    @staticmethod
    def build_media_resource(
        *,
        media_id: Optional[str] = None,
        image_id: str,
        patient_id: Optional[str] = None,
        encounter_id: Optional[str] = None,
        content_type: str,
        storage_uri: str,
        size_bytes: int,
        sha256_hash: str,
        width: int,
        height: int,
        created_at: str,
    ) -> Dict[str, Any]:
        mid = media_id or f"media-{uuid.uuid4().hex[:12]}"
        media = MediaResource(
            id=mid,
            identifier=[
                {"system": "https://healplus.local/fhir/identifier/media", "value": image_id}
            ],
            status="completed",
            media_type="image",
            modality={
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/media-modality",
                        "code": "photo",
                        "display": "Photography",
                    }
                ]
            },
            subject={"reference": f"Patient/{patient_id}"} if patient_id else {"reference": "Patient/anonymous"},
            encounter={"reference": f"Encounter/{encounter_id}"} if encounter_id else None,
            created_date_time=created_at,
            reason_code=[
                {
                    "coding": [
                        {
                            "system": "http://snomed.info/sct",
                            "code": "39135-9",
                            "display": "Wound evaluation photograph",
                        }
                    ]
                }
            ],
            content={
                "contentType": content_type,
                "url": storage_uri,
                "size": size_bytes,
                "hash": sha256_hash,
                "title": f"Wound clinical photograph ({width}x{height})",
            },
            note=[
                {
                    "text": (
                        "Fotografia clínica original preservada para triagem de qualidade, "
                        "acompanhamento de cicatrização e revisão especializada."
                    )
                }
            ],
        )
        return media.to_dict()

    @staticmethod
    def build_quality_observation(
        *,
        observation_id: Optional[str] = None,
        media_id: str,
        patient_id: Optional[str] = None,
        encounter_id: Optional[str] = None,
        status_code: str,  # "accepted", "rejected", "indeterminate"
        decision_pt: str,   # "aprovada", "nova_captura_necessaria"
        metrics: Dict[str, float],
        reasons: List[Dict[str, str]],
        created_at: str,
    ) -> Dict[str, Any]:
        oid = observation_id or f"obs-quality-{uuid.uuid4().hex[:12]}"
        observation = ObservationResource(
            id=oid,
            status="final",
            category=[
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "exam",
                            "display": "Exam",
                        }
                    ]
                }
            ],
            code={
                "coding": [
                    {
                        "system": "https://healplus.local/fhir/CodeSystem/image-quality",
                        "code": "technical-image-quality",
                        "display": "Qualidade técnica de fotografia clínica",
                    }
                ]
            },
            subject={"reference": f"Patient/{patient_id}"} if patient_id else {"reference": "Patient/anonymous"},
            encounter={"reference": f"Encounter/{encounter_id}"} if encounter_id else None,
            effective_date_time=created_at,
            interpretation=[
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                            "code": "N" if status_code == "accepted" else "A",
                            "display": "Normal" if status_code == "accepted" else "Abnormal",
                        }
                    ]
                }
            ],
            note=[
                {"text": f"Decisão técnica: {decision_pt.upper()} ({status_code}). {LIMITATION}"},
                *[{"text": f"{r.get('code')}: {r.get('message')}"} for r in reasons],
            ],
            component=[
                {
                    "code": {
                        "coding": [
                            {
                                "system": "https://healplus.local/fhir/CodeSystem/image-quality",
                                "code": name,
                                "display": name.replace("-", " ").capitalize(),
                            }
                        ]
                    },
                    "valueQuantity": {
                        "value": round(float(val), 4),
                        "unit": "pixels" if "width" in name or "height" in name else "score",
                        "system": "http://unitsofmeasure.org",
                        "code": "pixel" if "width" in name or "height" in name else "1",
                    },
                }
                for name, val in metrics.items()
            ],
        )
        res = observation.to_dict()
        res["focus"] = [{"reference": f"Media/{media_id}"}]
        return res

    @staticmethod
    def build_quality_bundle(media_resource: Dict[str, Any], observation_resource: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "resourceType": "Bundle",
            "id": f"bundle-quality-{uuid.uuid4().hex[:12]}",
            "type": "collection",
            "entry": [
                {"fullUrl": f"urn:uuid:{media_resource.get('id')}", "resource": media_resource},
                {"fullUrl": f"urn:uuid:{observation_resource.get('id')}", "resource": observation_resource},
            ],
        }

    @classmethod
    def validate_resource(cls, resource: Dict[str, Any]) -> List[str]:
        """Validate FHIR resource structure and schema, returning list of errors."""
        errors = validate_resource_structure(resource)
        res_type = resource.get("resourceType")
        if res_type == "Bundle":
            for entry in resource.get("entry", []):
                entry_res = entry.get("resource")
                if isinstance(entry_res, dict):
                    errors.extend(cls.validate_resource(entry_res))
            return errors

        try:
            model_errors = validate_with_fhir_models(resource)
            errors.extend(model_errors)
        except Exception as exc:
            errors.append(f"Model validation error: {exc}")
        return errors

    @classmethod
    def validate_with_hapi_fhir(cls, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Optionally validate with an external HAPI FHIR instance validator."""
        validator_url = os.getenv("HAPI_FHIR_VALIDATOR_URL")
        if not validator_url:
            # Fallback to local validation
            local_errors = cls.validate_resource(resource)
            return {
                "validated": True,
                "validator": "local_fhir_schema",
                "valid": len(local_errors) == 0,
                "errors": local_errors,
            }

        target_endpoint = f"{validator_url.rstrip('/')}/$validate"
        data = json.dumps(resource).encode("utf-8")
        req = urllib.request.Request(
            target_endpoint,
            data=data,
            headers={"Content-Type": "application/fhir+json", "Accept": "application/fhir+json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                outcome = json.loads(resp.read().decode("utf-8"))
                return {
                    "validated": True,
                    "validator": "hapi_fhir_server",
                    "valid": resp.status in (200, 201),
                    "operation_outcome": outcome,
                }
        except Exception as exc:
            local_errors = cls.validate_resource(resource)
            return {
                "validated": False,
                "validator": "hapi_fhir_fallback",
                "valid": len(local_errors) == 0,
                "warning": f"HAPI FHIR connection failed: {exc}",
                "errors": local_errors,
            }
