# -*- coding: utf-8 -*-
"""Clinical Image Quality Service orchestrating validation, OpenCV metrics, storage, and FHIR."""

from __future__ import annotations

import base64
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .assessment import Assessment, assess_image
from .decoder import DecodedImage, ImageInputError, decode_attachment
from .fhir_adapter import FHIRAdapter
from .repository import QualityEvaluationRecord, QualityRepository, get_quality_repository
from .storage import ImageStorageBackend, StoredImageRef, get_storage_backend


@dataclass
class QualityAssessmentResult:
    """Full outcome of a clinical image quality evaluation."""

    evaluation_id: str
    image_id: str
    patient_id: Optional[str]
    encounter_id: Optional[str]
    decision: str  # "aprovada" or "nova_captura_necessaria"
    status: str    # "accepted", "rejected", "indeterminate"
    approved: bool
    metrics: Dict[str, float]
    findings: List[Dict[str, str]]
    reasons_summary: List[str]
    storage_ref: Dict[str, Any]
    fhir_media: Dict[str, Any]
    fhir_observation: Dict[str, Any]
    fhir_bundle: Dict[str, Any]
    fhir_validation: Dict[str, Any]
    created_at: str

    @property
    def id(self) -> str:
        return self.evaluation_id

    @property
    def actionable_advice(self) -> Optional[str]:
        return " | ".join(self.reasons_summary) if self.reasons_summary else None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["id"] = self.evaluation_id
        data["actionable_advice"] = self.actionable_advice
        data["stored_image"] = data.get("storage_ref", {})
        return data


class ImageQualityService:
    """High-level service coordinating OpenCV assessment, original storage, and FHIR R4 integration."""

    def __init__(
        self,
        storage: Optional[ImageStorageBackend] = None,
        repository: Optional[QualityRepository] = None,
    ) -> None:
        self.storage = storage or get_storage_backend()
        self.repository = repository or get_quality_repository()

    def assess_image_bytes(
        self,
        raw_bytes: bytes,
        *,
        filename: str = "wound.jpg",
        content_type: str = "image/jpeg",
        patient_id: Optional[str] = None,
        encounter_id: Optional[str] = None,
        image_id: Optional[str] = None,
        consent: bool = True,
    ) -> QualityAssessmentResult:
        """Execute the 5-step clinical quality assessment workflow."""
        if not consent:
            raise ImageInputError("Confirme o consentimento para processar esta imagem antes de enviá-la.", 403)

        if not raw_bytes:
            raise ImageInputError("A imagem está vazia.", 400)

        img_id = image_id or f"img-{uuid.uuid4().hex[:12]}"
        eval_id = f"eval-{uuid.uuid4().hex}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Decode & validate image dimensions, format, and orientations safely
        attachment_payload = {
            "contentType": content_type,
            "data": base64.b64encode(raw_bytes).decode("ascii"),
        }
        decoded: DecodedImage = decode_attachment(attachment_payload)

        # 2. Run OpenCV + Pillow quality assessment (sharpness, lighting, resolution, contrast, glare, noise)
        assessment: Assessment = assess_image(decoded)

        # 3. Formulate clinical decision
        is_approved = assessment.status == "accepted"
        decision_pt = "aprovada" if is_approved else "nova_captura_necessaria"

        findings_list = [
            {"code": f.code, "severity": f.severity, "message": f.message}
            for f in assessment.findings
        ]
        reasons_summary = [f.message for f in assessment.findings]

        # 4. Securely store original unaltered bytes and record transformations applied during analysis
        transformations = [
            "exif_orientation_applied",
            "rgb_normalized",
            f"analysis_scaled_to_{decoded.rgb.shape[1]}x{decoded.rgb.shape[0]}",
        ]
        stored_ref: StoredImageRef = self.storage.save_image(
            raw_bytes,
            filename=filename,
            content_type=content_type,
            transformations=transformations,
            metadata={
                "image_id": img_id,
                "patient_id": patient_id,
                "encounter_id": encounter_id,
                "evaluation_id": eval_id,
                "original_dimensions": {"width": decoded.width, "height": decoded.height},
            },
        )

        # 5. Assemble and validate FHIR R4 Media and Observation
        media_id = f"media-{eval_id[:12]}"
        obs_id = f"obs-{eval_id[:12]}"

        fhir_media = FHIRAdapter.build_media_resource(
            media_id=media_id,
            image_id=img_id,
            patient_id=patient_id,
            encounter_id=encounter_id,
            content_type=content_type,
            storage_uri=stored_ref.uri,
            size_bytes=stored_ref.size_bytes,
            sha256_hash=stored_ref.sha256,
            width=decoded.width,
            height=decoded.height,
            created_at=now_iso,
        )

        fhir_observation = FHIRAdapter.build_quality_observation(
            observation_id=obs_id,
            media_id=media_id,
            patient_id=patient_id,
            encounter_id=encounter_id,
            status_code=assessment.status,
            decision_pt=decision_pt,
            metrics=assessment.metrics,
            reasons=findings_list,
            created_at=now_iso,
        )

        fhir_bundle = FHIRAdapter.build_quality_bundle(fhir_media, fhir_observation)
        validation_report = FHIRAdapter.validate_with_hapi_fhir(fhir_bundle)

        # Persist evaluation in database repository
        record = QualityEvaluationRecord(
            id=eval_id,
            image_id=img_id,
            patient_id=patient_id,
            encounter_id=encounter_id,
            storage_key=stored_ref.storage_key,
            sha256=stored_ref.sha256,
            mime_type=content_type,
            decision=decision_pt,
            status_code=assessment.status,
            metrics=assessment.metrics,
            reasons=findings_list,
            fhir_media_id=media_id,
            fhir_observation_id=obs_id,
            created_at=now_iso,
        )
        self.repository.save_evaluation(record)

        return QualityAssessmentResult(
            evaluation_id=eval_id,
            image_id=img_id,
            patient_id=patient_id,
            encounter_id=encounter_id,
            decision=decision_pt,
            status=assessment.status,
            approved=is_approved,
            metrics=assessment.metrics,
            findings=findings_list,
            reasons_summary=reasons_summary,
            storage_ref=stored_ref.to_dict(),
            fhir_media=fhir_media,
            fhir_observation=fhir_observation,
            fhir_bundle=fhir_bundle,
            fhir_validation=validation_report,
            created_at=now_iso,
        )

    def get_evaluation(self, evaluation_id: str) -> Optional[QualityEvaluationRecord]:
        return self.repository.get_evaluation(evaluation_id)

    def list_patient_evaluations(self, patient_id: str) -> List[QualityEvaluationRecord]:
        return self.repository.list_evaluations_by_patient(patient_id)
