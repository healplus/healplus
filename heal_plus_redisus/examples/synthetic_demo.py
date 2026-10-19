"""End-to-end demo made from geometric pixels; no photographs or patients."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import secrets
from uuid import UUID, uuid4

import numpy as np
from PIL import Image

from ..src.domain.clinical_models import ClinicalAssessment, PatientReference, PhotoConsent
from ..src.domain.rbac_audit import AuditStore, Principal, Role
from ..src.experiment import ExperimentManifest, load_manifest
from ..src.experiment_runner import ExperimentCase, run_experiment
from ..src.privacy import sanitize_upload
from ..src.safety import ASSISTIVE_DISCLAIMER
from ..src.service import SprintsService
from ..src.sprint1_pipeline.cascade_evaluator import CascadeEvaluator
from ..src.sprint1_pipeline.hybrid_segmenter import HybridSegmenter
from ..src.sprint1_pipeline.roi_handler import ROI
from ..src.sprint2_clinical_visual.guided_capture_validator import CaptureMeasurements, GuidedCaptureValidator
from ..src.sprint2_clinical_visual.statistical_analyzer import StatisticalAnalyzer
from ..src.sprint2_clinical_visual.visual_inspector import ClinicalVisualInspector, VisualInspection


class NoDetector:
    """Explicit absence of detector weights; never a fake YOLO prediction."""

    def detect(self, image_rgb):
        return []


def geometry():
    rng = np.random.default_rng(42)
    rgb = rng.integers(60, 190, (128, 160, 3), dtype=np.uint8)
    mask = np.zeros(rgb.shape[:2], bool)
    mask[35:85, 45:100] = True
    rgb[mask] = [90, 130, 180]
    raw = io.BytesIO()
    Image.fromarray(rgb).save(raw, format="PNG")
    return raw.getvalue(), mask


def run_demo(output_dir: str | Path) -> dict:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    raw, mask = geometry()
    clean = sanitize_upload(raw, "image/png", consent=True, privacy_reviewed=True)
    image_id = UUID("20000000-0000-4000-8000-000000000001")
    manifest_data = load_manifest(
        Path(__file__).resolve().parents[1] / "config" / "experiment_manifest.yaml"
    ).model_dump(mode="json")
    manifest_data["items"] = [
        {
            "image_id": str(image_id),
            "patient_group": "30000000-0000-4000-8000-000000000001",
            "split": "test",
            "sha256": clean.sha256,
            "width": clean.width,
            "height": clean.height,
            "skin_tone": "desconhecido",
        }
    ]
    manifest = ExperimentManifest.model_validate(manifest_data)
    roi = ROI("synthetic_roi", (40, 30, 105, 90))
    researcher = Principal(user_id=uuid4(), tenant_id=uuid4(), role=Role.PESQUISADOR, authenticated=True)
    # The temporary key is only for a disposable synthetic database, never real care.
    # Production supplies a durable institutional key and externally anchored checkpoints.
    audit = AuditStore(output / "synthetic-audit.db", secrets.token_bytes(32))
    service = SprintsService(output / "synthetic-care.db", audit)
    try:
        evaluation = run_experiment(
            researcher,
            manifest,
            [ExperimentCase(image_id, clean, (roi,), {roi.id: mask}, {"etiology": "unknown"})],
            CascadeEvaluator(HybridSegmenter(), NoDetector()),
            audit,
            output / "experiment",
            synthetic_abstention=True,
        )[0]
        now = datetime.now(timezone.utc)
        patient_id, wound_id, assessment_id, actor_id = (uuid4() for _ in range(4))
        actor = Principal(
            user_id=actor_id,
            tenant_id=researcher.tenant_id,
            role=Role.ENFERMEIRO,
            authenticated=True,
            authorized_patient_ids=frozenset({patient_id}),
        )
        patient = PatientReference(patient_id=patient_id, pseudonym="pt_synthetic_demo")
        review = {"reviewer_id": actor_id, "role": "Enfermeiro", "reviewed_at": now, "affirmed_by_professional": True}
        consent = PhotoConsent(
            consent_id=uuid4(),
            recorded_at=now - timedelta(seconds=1),
            capture_authorized=True,
            care_use_authorized=True,
        )
        service.register_patient(actor, patient)
        service.register_wound(actor, patient_id, wound_id)
        image = service.upload_image(
            actor,
            patient_id=patient_id,
            wound_id=wound_id,
            assessment_id=assessment_id,
            raw=raw,
            content_type="image/png",
            consent=consent,
            privacy_reviewed=True,
            captured_at=now,
        )
        assessment = ClinicalAssessment(
            assessment_id=assessment_id,
            patient=patient,
            wound_id=wound_id,
            professional_id=actor_id,
            assessed_at=now,
            history={"context": "Demonstração exclusivamente sintética; sem paciente real."},
            anatomical_location={"region": "Região fictícia", "laterality": "nao_informada"},
            wound_type="nao_determinada",
            dimensions={"method": "nao_mensuravel", "unavailable_reason": "Geometria sintética sem escala física."},
            predominant_tissue="nao_classificado_baixa_confianca",
            infection_signs=[],
            exudate={"amount": "nao_avaliado", "appearance": "nao_avaliado"},
            edges=["nao_avaliadas"],
            perilesional_skin=["nao_avaliada"],
            images=[image],
            temporal_evolution={"baseline": True, "observations": "Primeiro registro sintético."},
            professional_observations="Sem observações clínicas: pixels gerados por código.",
            clinical_report="Demonstração de integração; todos os pixels permanecem sem classificação tecidual.",
            care_plan={
                "applicable": False,
                "continuity_guidance": "Sem conduta: demonstração sintética.",
                "review": review,
            },
            review=review,
        )
        service.save_assessment(actor, assessment)
        service.analyze(actor, assessment_id, image.image_id, rois=[roi], segmenter=HybridSegmenter())
        bundle = service.export_fhir(actor, assessment_id, confirmed=True)
        (output / "synthetic-bundle.json").write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        capture = GuidedCaptureValidator().validate(
            clean.rgb, CaptureMeasurements(consent_to_capture=True, privacy_checked=True, identifying_exif_removed=True)
        )
        annotation = VisualInspection(
            image_id=str(image_id),
            dataset_id=manifest.dataset.name,
            category=evaluation.record.category,
            dice=evaluation.record.dice_cascade,
            detector_iou=evaluation.record.detector_iou,
            tia=evaluation.record.tia_percent / 100,
        )
        inspection = ClinicalVisualInspector().inspect(annotation)
        statistics = StatisticalAnalyzer().analyze([annotation])
        summary = {
            "synthetic_only": True,
            "model_weights_available": False,
            "category": evaluation.record.category,
            "capture": asdict(capture),
            "inspection": asdict(inspection),
            "statistics": asdict(statistics),
            "disclaimer": ASSISTIVE_DISCLAIMER,
        }
        (output / "sprint2-summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
        )
        return {
            "output": str(output.resolve()),
            "bundle_resources": len(bundle["entry"]),
            "synthetic_only": True,
            "disclaimer": ASSISTIVE_DISCLAIMER,
        }
    finally:
        service.close()
        audit.close()
