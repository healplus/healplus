"""CV01–CV10 / MT01–MT13: technical evidence using exclusively synthetic data.

CV03 usability, CV05 visual review and CV08 CEP approval additionally require
human/institutional evidence; passing tests never manufactures those approvals.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
from uuid import uuid4

import numpy as np
from PIL import Image
import pytest
from pydantic import ValidationError

from heal_plus_redisus.src.domain.clinical_models import ClinicalAssessment, PatientReference, PhotoConsent
from heal_plus_redisus.src.domain.rbac_audit import AccessDenied, AuditStore, Principal, Role
from heal_plus_redisus.src.experiment import ExperimentManifest, freeze_manifest, load_manifest
from heal_plus_redisus.src.interoperability.fhir_exporter import SprintsFHIRExporter, validate_bundle
from heal_plus_redisus.src.privacy import sanitize_upload
from heal_plus_redisus.src.safety import ASSISTIVE_DISCLAIMER
from heal_plus_redisus.src.service import SprintsService
from heal_plus_redisus.tests.test_domain import assessment_payload

PACKAGE = Path(__file__).resolve().parents[1]


def photograph():
    # Generated texture is not a wound and must never be used as clinical evidence.
    rng = np.random.default_rng(42)
    rgb = rng.integers(40, 200, (96, 112, 3), dtype=np.uint8)
    stream = io.BytesIO()
    exif = Image.Exif()
    exif[270] = "SYNTHETIC_IDENTIFIER_MUST_BE_REMOVED"
    exif[274] = 6
    Image.fromarray(rgb).save(stream, format="JPEG", exif=exif)
    return stream.getvalue()


@pytest.fixture
def workflow(tmp_path):
    payload = assessment_payload()
    patient = PatientReference.model_validate(payload["patient"])
    actor = Principal(
        user_id=payload["professional_id"],
        tenant_id=uuid4(),
        role=Role.ENFERMEIRO,
        authenticated=True,
        authorized_patient_ids=frozenset({patient.patient_id}),
    )
    audit = AuditStore(tmp_path / "audit.db", b"synthetic-testing-integrity-key-32!")
    service = SprintsService(tmp_path / "care.db", audit)
    service.register_patient(actor, patient)
    service.register_wound(actor, patient.patient_id, payload["wound_id"])
    image = service.upload_image(
        actor,
        patient_id=patient.patient_id,
        wound_id=payload["wound_id"],
        assessment_id=payload["assessment_id"],
        raw=photograph(),
        content_type="image/jpeg",
        captured_at=payload["images"][0]["captured_at"],
        consent=PhotoConsent.model_validate(payload["images"][0]["consent"]),
        privacy_reviewed=True,
        scale_present=True,
    )
    payload["images"] = [image.model_dump(mode="json")]
    assessment = ClinicalAssessment.model_validate(payload)
    service.save_assessment(actor, assessment)
    yield service, actor, assessment, audit
    service.close()
    audit.close()


def test_CV01_MT02_MT03_create_edit_read_persist_versioned(workflow):
    service, actor, assessment, _ = workflow
    assert service.get_assessment(actor, assessment.assessment_id) == assessment
    changed = assessment.model_dump(mode="json")
    changed["professional_observations"] = "Observação sintética revista pelo profissional."
    updated = ClinicalAssessment.model_validate(changed)
    assert service.save_assessment(actor, updated) == 2
    assert service.get_assessment(actor, assessment.assessment_id) == updated
    assert service.history(actor, assessment.patient.patient_id, assessment.wound_id) == (updated,)
    assert service.connection.execute("SELECT COUNT(*) FROM sprint_assessment_versions").fetchone()[0] == 2


def test_CV01_MT02_patient_update_requires_care_link(workflow):
    service, actor, assessment, _ = workflow
    patient = PatientReference(patient_id=assessment.patient.patient_id, pseudonym="pt_synthetic02")
    service.register_patient(actor, patient)
    assert service.get_patient(actor, patient.patient_id) == patient
    other = actor.model_copy(update={"user_id": uuid4(), "authorized_patient_ids": frozenset()})
    # Creation is idempotent for an unassigned nurse; it never overwrites or
    # discloses whether this opaque ID already exists.
    service.register_patient(other, PatientReference(patient_id=patient.patient_id, pseudonym="pt_forbidden01"))
    assert service.get_patient(actor, patient.patient_id) == patient
    with pytest.raises(AccessDenied):
        service.get_patient(other, patient.patient_id)


def test_CV02_CV09_MT01_MT08_user_and_tenant_switch(workflow):
    service, actor, assessment, audit = workflow
    for changes in (
        {"user_id": uuid4(), "authorized_patient_ids": frozenset()},
        {"tenant_id": uuid4()},
        {"authenticated": False},
        {"role": Role.PESQUISADOR},
        {"role": Role.ADMINISTRADOR},
    ):
        other = actor.model_copy(update=changes)
        with pytest.raises((AccessDenied, LookupError)):
            service.get_assessment(other, assessment.assessment_id)
    assert audit.verify_integrity()


def test_CV03_MT03_structured_reference_workflow_preserves_required_data(workflow):
    service, actor, assessment, _ = workflow
    loaded = service.get_assessment(actor, assessment.assessment_id)
    assert loaded.images[0].patient_id == loaded.patient.patient_id
    assert loaded.review.affirmed_by_professional
    assert loaded.temporal_evolution.baseline
    assert loaded.care_plan.continuity_guidance
    assert loaded.disclaimer == ASSISTIVE_DISCLAIMER


def test_CV04_MT04_strip_exif_gps_comments_and_apply_orientation():
    result = sanitize_upload(photograph(), "image/jpeg", consent=True, privacy_reviewed=True)
    assert (result.width, result.height) == (96, 112)
    with Image.open(io.BytesIO(result.content)) as image:
        assert image.getexif() == {}
        assert not image.info
    assert b"SYNTHETIC_IDENTIFIER" not in result.content
    assert result.sha256 == hashlib.sha256(result.content).hexdigest()


@pytest.mark.parametrize("consent,review", [(False, True), (True, False), (False, False)])
def test_CV04_CV08_CV09_no_upload_without_consent_privacy(consent, review):
    with pytest.raises(PermissionError):
        sanitize_upload(photograph(), "image/jpeg", consent=consent, privacy_reviewed=review)


@pytest.mark.parametrize(
    "raw,mime",
    [(b"invalid", "image/png"), (b"", "image/jpeg"), (None, "image/jpeg")],
    ids=["corrupt", "empty", "oversize"],
)
def test_CV04_MT04_bounded_untrusted_upload(raw, mime):
    if raw is None:
        raw = b"x" * (10 * 1024 * 1024 + 1)
    with pytest.raises(ValueError):
        sanitize_upload(raw, mime, consent=True, privacy_reviewed=True)


def test_CV04_MT04_image_cannot_be_forged_or_relinked(workflow):
    service, actor, assessment, _ = workflow
    changed = assessment.model_dump(mode="json")
    changed["images"][0]["content_sha256"] = "b" * 64
    with pytest.raises(ValueError):
        service.save_assessment(actor, ClinicalAssessment.model_validate(changed))
    pixels = service.image_pixels(actor, assessment.images[0].image_id)
    assert pixels.shape == (112, 96, 3)


def test_CV05_MT05_multiple_rois_integrated_abstention(workflow):
    from heal_plus_redisus.src.sprint1_pipeline.roi_handler import ROI
    from heal_plus_redisus.src.sprint1_pipeline.hybrid_segmenter import HybridSegmenter

    service, actor, assessment, _ = workflow
    rois = [ROI("roi1", (10, 10, 35, 35)), ROI("roi2", (40, 40, 80, 80))]
    summary = service.analyze(
        actor, assessment.assessment_id, assessment.images[0].image_id, rois=rois, segmenter=HybridSegmenter()
    )
    assert len(summary["rois"]) == 2
    for result in summary["rois"]:
        assert result["tissue_percentages"]["nao_classificado_baixa_confianca"] == 100
        assert sum(result["tissue_percentages"].values()) == 100
        assert result["review_required"]
    assert summary["disclaimer"] == ASSISTIVE_DISCLAIMER
    # Recorded analysis travels to the actual export, not a disconnected mock.
    bundle = service.export_fhir(actor, assessment.assessment_id, confirmed=True)
    assert "assistive-" in json.dumps(bundle)
    changed = assessment.model_dump(mode="json")
    changed["professional_observations"] = "Registro revisto: resultados anteriores ficam invalidados."
    service.save_assessment(actor, ClinicalAssessment.model_validate(changed))
    assert service.connection.execute("SELECT COUNT(*) FROM sprint_analyses").fetchone()[0] == 0


@pytest.mark.parametrize("kind", ["collection", "transaction"])
def test_CV06_MT07_MT12_fhir_official_schema_closed_references(workflow, kind):
    service, actor, assessment, _ = workflow
    bundle = service.export_fhir(actor, assessment.assessment_id, confirmed=True, bundle_type=kind)
    validate_bundle(bundle)
    resources = {entry["resource"]["resourceType"]: entry["resource"] for entry in bundle["entry"]}
    assert resources["DiagnosticReport"]["conclusion"] == ASSISTIVE_DISCLAIMER
    assert resources["Observation"]["status"] == "preliminary"
    assert "name" not in resources["Patient"]
    resources["Observation"]["subject"]["reference"] = "Patient/not-in-this-bundle"
    with pytest.raises(ValueError, match="Bundle inválido"):
        validate_bundle(bundle)


def test_CV06_MT07_export_requires_explicit_action(workflow):
    service, actor, assessment, _ = workflow
    with pytest.raises(AccessDenied):
        service.export_fhir(actor, assessment.assessment_id, confirmed=False)


def test_CV07_MT09_MT11_frozen_manifest_runtime_and_license(tmp_path):
    manifest = load_manifest(PACKAGE / "config" / "experiment_manifest.yaml")
    target = tmp_path / "manifest.json"
    digest = freeze_manifest(manifest, target)
    assert digest == hashlib.sha256(target.read_bytes()).hexdigest()
    assert json.loads(target.read_text(encoding="utf-8"))["runtime"]["python"]
    with pytest.raises(FileExistsError):
        freeze_manifest(manifest, target)
    with pytest.raises(ValueError):
        manifest.require_evaluable()
    data = manifest.model_dump(mode="json")
    data["dataset"]["license_reviewed"] = False
    with pytest.raises(ValidationError):
        ExperimentManifest.model_validate(data)


def test_CV07_MT09_prevent_patient_and_image_split_leakage():
    data = load_manifest(PACKAGE / "config" / "experiment_manifest.yaml").model_dump(mode="json")
    item = {
        "image_id": str(uuid4()),
        "patient_group": str(uuid4()),
        "sha256": "a" * 64,
        "width": 100,
        "height": 100,
        "skin_tone": "claro",
        "split": "train",
    }
    data["items"] = [item, {**item, "image_id": str(uuid4()), "split": "test"}]
    with pytest.raises(ValidationError):
        ExperimentManifest.model_validate(data)


def test_CV08_MT10_real_research_requires_cep_tcle_and_plan(workflow):
    service, actor, assessment, _ = workflow
    with pytest.raises(PermissionError):
        service.export_fhir(actor, assessment.assessment_id, confirmed=True, research=True)
    data = load_manifest(PACKAGE / "config" / "experiment_manifest.yaml").model_dump(mode="json")
    data["dataset"]["kind"] = "clinical"
    with pytest.raises(ValidationError):
        ExperimentManifest.model_validate(data)


def test_CV08_MT10_research_export_omits_free_text_and_images(workflow):
    _, _, assessment, _ = workflow
    payload = assessment.model_dump(mode="json")
    payload["professional_observations"] = "SYNTHETIC_FREE_TEXT_SENTINEL"
    payload["history"]["context"] = "SYNTHETIC_FREE_TEXT_SENTINEL"
    payload["anatomical_location"]["region"] = "SYNTHETIC_FREE_TEXT_SENTINEL"
    for image in payload["images"]:
        image["consent"]["research_use_authorized"] = True
        image["consent"]["research_governance"] = {
            "ethics_approval_reference": "SYNTHETIC-CEP-EXAMPLE",
            "informed_consent_reference": "SYNTHETIC-TCLE-EXAMPLE",
            "approved_at": assessment.assessed_at.isoformat(),
            "permitted_purpose": "Teste sintético, sem participantes reais.",
        }
    bundle = SprintsFHIRExporter().export(ClinicalAssessment.model_validate(payload), research=True)
    encoded = json.dumps(bundle)
    assert "SYNTHETIC_FREE_TEXT_SENTINEL" not in encoded
    assert "SYNTHETIC-CEP" not in encoded
    assert assessment.patient.pseudonym not in encoded
    assert str(assessment.patient.patient_id) not in encoded
    assert assessment.assessed_at.isoformat() not in encoded
    assert not any("data" in entry["resource"].get("content", {}) for entry in bundle["entry"])


def test_CV09_MT08_audit_contains_no_clinical_payload(workflow):
    service, actor, assessment, audit = workflow
    service.get_assessment(actor, assessment.assessment_id)
    events = "\n".join(event.model_dump_json() for event in audit.events())
    assert assessment.professional_observations not in events
    assert assessment.patient.pseudonym not in events
    assert str(assessment.patient.patient_id) not in events
    assert assessment.images[0].content_sha256 not in events
    assert "synthetic-testing-integrity-key" not in events


def test_MT06_history_links_same_wound_in_time(workflow):
    service, actor, assessment, _ = workflow
    now = datetime.now(timezone.utc) + timedelta(minutes=1)
    payload = assessment.model_dump(mode="json")
    next_id = uuid4()
    image = service.upload_image(
        actor,
        patient_id=assessment.patient.patient_id,
        wound_id=assessment.wound_id,
        assessment_id=next_id,
        raw=photograph(),
        content_type="image/jpeg",
        captured_at=now,
        consent=assessment.images[0].consent,
        privacy_reviewed=True,
    )
    payload.update(
        assessment_id=str(next_id),
        assessed_at=now.isoformat(),
        images=[image.model_dump(mode="json")],
        temporal_evolution={
            "baseline": False,
            "previous_assessment_id": str(assessment.assessment_id),
            "observations": "Comparação documental, sem inferência de cicatrização.",
        },
    )
    payload["review"]["reviewed_at"] = now.isoformat()
    service.save_assessment(actor, ClinicalAssessment.model_validate(payload))
    assert len(service.history(actor, assessment.patient.patient_id, assessment.wound_id)) == 2


def test_MT13_human_care_plan_and_procedure_export(workflow):
    _, _, assessment, _ = workflow
    payload = assessment.model_dump(mode="json")
    payload["care_plan"].update(
        applicable=True,
        procedures=["Procedimento sintético registrado pelo profissional"],
        supplies=["Insumo sintético"],
    )
    bundle = SprintsFHIRExporter().export(ClinicalAssessment.model_validate(payload))
    assert {"CarePlan", "Procedure"} <= {entry["resource"]["resourceType"] for entry in bundle["entry"]}


def test_MT13_service_rejects_forged_nested_professional(workflow):
    service, actor, assessment, _ = workflow
    payload = assessment.model_dump(mode="json")
    payload["care_plan"]["review"]["reviewer_id"] = str(uuid4())
    with pytest.raises(PermissionError):
        service.save_assessment(actor, ClinicalAssessment.model_validate(payload))


def test_MT02_MT03_committed_records_survive_a_new_service_connection(workflow):
    service, actor, assessment, audit = workflow
    database = service.connection.execute("PRAGMA database_list").fetchone()[2]
    reopened = SprintsService(database, audit)
    try:
        assert reopened.get_assessment(actor, assessment.assessment_id) == assessment
        assert reopened.image_pixels(actor, assessment.images[0].image_id).shape == (112, 96, 3)
    finally:
        reopened.close()


def test_analysis_changed_during_inference_cannot_be_saved_as_current(workflow):
    from heal_plus_redisus.src.sprint1_pipeline.hybrid_segmenter import HybridSegmenter
    from heal_plus_redisus.src.sprint1_pipeline.roi_handler import ROI

    service, actor, assessment, audit = workflow
    database = service.connection.execute("PRAGMA database_list").fetchone()[2]
    writer = SprintsService(database, audit)

    class EditDuringSegmentation(HybridSegmenter):
        def segment(self, *args, **kwargs):
            payload = assessment.model_dump(mode="json")
            payload["professional_observations"] = "Edição concorrente sintética."
            writer.save_assessment(actor, ClinicalAssessment.model_validate(payload))
            return super().segment(*args, **kwargs)

    try:
        with pytest.raises(ValueError, match="mudou durante"):
            service.analyze(
                actor,
                assessment.assessment_id,
                assessment.images[0].image_id,
                rois=[ROI("one", (10, 10, 35, 35))],
                segmenter=EditDuringSegmentation(),
            )
        assert service.connection.execute("SELECT COUNT(*) FROM sprint_analyses").fetchone()[0] == 0
    finally:
        writer.close()


def test_fhir_export_uses_one_current_revision_snapshot(workflow, monkeypatch):
    service, actor, assessment, audit = workflow
    database = service.connection.execute("PRAGMA database_list").fetchone()[2]
    writer = SprintsService(database, audit)
    original_load = service._load_assessment

    def load_then_edit(principal, identifier):
        previous = original_load(principal, identifier)
        payload = previous.model_dump(mode="json")
        payload["dimensions"]["length_cm"] = 3
        writer.save_assessment(actor, ClinicalAssessment.model_validate(payload))
        return previous

    monkeypatch.setattr(service, "_load_assessment", load_then_edit)
    try:
        bundle = service.export_fhir(actor, assessment.assessment_id, confirmed=True)
        resources = {entry["resource"]["resourceType"]: entry["resource"] for entry in bundle["entry"]}
        length = next(
            component for component in resources["Observation"]["component"] if component["code"]["text"] == "length_cm"
        )
        assert length["valueQuantity"]["value"] == 3
        assert resources["DiagnosticReport"]["extension"][0]["valueInteger"] == 2
    finally:
        writer.close()


def test_CV04_capture_protocol_survives_ingestion_and_fhir(workflow):
    from heal_plus_redisus.src.domain.capture_models import CaptureMeasurements

    service, actor, assessment, _ = workflow
    protocol = CaptureMeasurements(
        distance_cm=25,
        distance_source="medida_manual",
        angle_to_wound_plane_deg=90,
        angle_source="plano_medido_manualmente",
        consent_to_capture=True,
        privacy_checked=True,
        identifying_exif_removed=False,
        scale_present=True,
        scale_next_to_wound=True,
        framing_complete=True,
        neutral_background=True,
    )
    image = service.upload_image(
        actor,
        patient_id=assessment.patient.patient_id,
        wound_id=assessment.wound_id,
        assessment_id=assessment.assessment_id,
        raw=photograph(),
        content_type="image/jpeg",
        captured_at=assessment.assessed_at,
        consent=assessment.images[0].consent,
        privacy_reviewed=True,
        capture_measurements=protocol,
        debridement_phase="pos_desbridamento",
    )
    assert image.capture_protocol.identifying_exif_removed is True
    assert image.capture_status == "indeterminado"  # no perilesional lighting reference was provided
    payload = assessment.model_dump(mode="json")
    payload["images"].append(image.model_dump(mode="json"))
    service.save_assessment(actor, ClinicalAssessment.model_validate(payload))
    bundle = service.export_fhir(actor, assessment.assessment_id, confirmed=True)
    media = [entry["resource"] for entry in bundle["entry"] if entry["resource"]["resourceType"] == "Media"]
    extensions = [extension for resource in media for extension in resource["extension"]]
    exported = next(extension for extension in extensions if extension["url"].endswith("capture-protocol"))
    assert json.loads(exported["valueString"])["distance_cm"] == 25
    assert any(extension.get("valueCode") == "pos_desbridamento" for extension in extensions)


def test_MT12_device_perfusion_neuropathy_preserve_human_records(workflow):
    _, _, assessment, _ = workflow
    payload = assessment.model_dump(mode="json")
    review = payload["review"]
    payload["device_association"] = {
        "device_type": "Dispositivo sintético",
        "contact_region": "Região sintética",
        "mucosal_contact": False,
        "use_duration_hours": 2,
        "review": review,
    }
    payload["perfusion"] = {
        "ankle_brachial_index": 0.8,
        "toe_pressure_mmhg": 50,
        "observations": "Dado sintético registrado por profissional.",
        "review": review,
    }
    payload["neuropathy"] = {
        "protective_sensation": "nao_avaliada",
        "examination_method": "Não avaliado neste exemplo",
        "observations": "Registro sintético",
        "review": review,
    }
    bundle = SprintsFHIRExporter().export(ClinicalAssessment.model_validate(payload))
    resources = {entry["resource"]["resourceType"]: entry["resource"] for entry in bundle["entry"]}
    assert resources["DeviceUseStatement"]["bodySite"]["text"] == "Região sintética"
    component = next(
        item
        for item in resources["Observation"]["component"]
        if item["code"]["text"] == "professional-perfusion-toe_pressure_mmhg"
    )
    assert component["valueQuantity"]["value"] == 50
    assert component["valueQuantity"]["code"] == "mm[Hg]"


def test_CV10_traceability_contains_all_source_criteria():
    matrix = json.loads((PACKAGE / "config" / "validation_matrix.json").read_text(encoding="utf-8"))
    assert set(matrix["criteria"]) == {f"CV{i:02}" for i in range(1, 11)}
    assert set(matrix["traceability"]) == {f"MT{i:02}" for i in range(1, 14)}
    assert matrix["criteria"]["CV03"]["human_evidence_required"]
    assert matrix["criteria"]["CV08"]["human_evidence_required"]
