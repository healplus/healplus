"""Synthetic-only clinical validation and authorization regression tests."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import sqlite3
from uuid import uuid4

import pytest
from pydantic import ValidationError

from heal_plus_redisus.src.domain.clinical_models import (
    CEAPClassification,
    ClinicalAssessment,
    LPPClassification,
    TissueComposition,
    WIfIClassification,
    WoundDimensions,
)
from heal_plus_redisus.src.domain.rbac_audit import (
    AccessDenied,
    AccessPolicy,
    Action,
    AuditEvent,
    AuditIntegrityError,
    AuditOutcome,
    AuditReason,
    AuditStore,
    DataClass,
    Principal,
    ResourceScope,
    Role,
    authorize,
    decide_access,
)
from heal_plus_redisus.src.safety import ASSISTIVE_DISCLAIMER
from heal_plus_redisus.src.domain.capture_models import CaptureMeasurements


def assessment_payload():
    now = datetime.now(timezone.utc)
    patient, wound, assessment, professional = (uuid4() for _ in range(4))
    review = dict(reviewer_id=professional, role="Enfermeiro", reviewed_at=now, affirmed_by_professional=True)
    return dict(
        assessment_id=assessment,
        patient=dict(patient_id=patient, pseudonym="pt_synthetic01"),
        wound_id=wound,
        assessed_at=now,
        professional_id=professional,
        history=dict(context="Registro exclusivamente sintético."),
        anatomical_location=dict(region="perna", laterality="direita"),
        wound_type="ulcera_venosa",
        dimensions=dict(length_cm=2, width_cm=1, method="manual_com_escala"),
        predominant_tissue="nao_classificado_baixa_confianca",
        tissue_composition=dict(
            granulacao=0, esfacelo_fibrina=0, necrose=0, epitelizacao=0, nao_classificado_baixa_confianca=100
        ),
        infection_signs=[],
        exudate=dict(amount="nao_avaliado", appearance="nao_avaliado"),
        edges=["nao_avaliadas"],
        perilesional_skin=["nao_avaliada"],
        images=[
            dict(
                image_id=uuid4(),
                patient_id=patient,
                wound_id=wound,
                assessment_id=assessment,
                captured_at=now,
                captured_by=professional,
                purpose="acompanhamento_assistencial",
                consent=dict(
                    consent_id=uuid4(),
                    recorded_at=now - timedelta(minutes=1),
                    capture_authorized=True,
                    care_use_authorized=True,
                ),
                content_sha256="a" * 64,
                exif_removed=True,
            )
        ],
        temporal_evolution=dict(baseline=True, observations="Primeiro registro disponível."),
        professional_observations="Observação sintética.",
        clinical_report="Relatório sintético revisado.",
        care_plan=dict(applicable=False, continuity_guidance="Registro sintético sem conduta.", review=review),
        review=review,
    )


def test_full_rc_record_round_trip_disclaimer():
    model = ClinicalAssessment.model_validate(assessment_payload())
    assert ClinicalAssessment.model_validate_json(model.model_dump_json()) == model
    assert model.disclaimer == ASSISTIVE_DISCLAIMER
    assert model.pain is None
    assert model.tissue_composition.nao_classificado_baixa_confianca == 100


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1, 101])
def test_percentage_never_nan_out_of_range(bad):
    with pytest.raises(ValidationError):
        TissueComposition(
            granulacao=bad, esfacelo_fibrina=0, necrose=0, epitelizacao=0, nao_classificado_baixa_confianca=100
        )


def test_composition_requires_all_five_classes_and_total():
    with pytest.raises(ValidationError):
        TissueComposition(granulacao=90, esfacelo_fibrina=0, necrose=0, epitelizacao=0)
    with pytest.raises(ValidationError):
        TissueComposition(
            granulacao=90, esfacelo_fibrina=0, necrose=0, epitelizacao=0, nao_classificado_baixa_confianca=0
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.update(assessed_at=datetime.now()),
        lambda p: p["patient"].update(pseudonym="nome de paciente"),
        lambda p: p["patient"].update(name="Identificador proibido"),
        lambda p: p["images"][0].update(patient_id=uuid4()),
        lambda p: p["images"][0].update(wound_id=uuid4()),
        lambda p: p["images"][0].update(assessment_id=uuid4()),
        lambda p: p["images"][0].update(exif_removed=False),
        lambda p: p["images"][0]["consent"].update(capture_authorized=False),
        lambda p: p["images"][0]["consent"].update(research_use_authorized=True),
        lambda p: p["images"][0].update(purpose="pesquisa_aprovada"),
        lambda p: p["review"].update(affirmed_by_professional=False),
        lambda p: p.update(images=[]),
        lambda p: p.update(edges=[]),
        lambda p: p["dimensions"].update(length_cm=float("nan")),
        lambda p: p["temporal_evolution"].update(previous_assessment_id=uuid4()),
        lambda p: p.update(disclaimer="Conclusão autônoma"),
    ],
)
def test_clinical_privacy_links_and_missing_consent_rejected(mutation):
    payload = assessment_payload()
    mutation(payload)
    with pytest.raises(ValidationError):
        ClinicalAssessment.model_validate(payload)


def test_unavailable_measurement_requires_reason_and_never_invents_values():
    with pytest.raises(ValidationError):
        WoundDimensions(method="nao_mensuravel")
    model = WoundDimensions(method="nao_mensuravel", unavailable_reason="Sem escala validada.")
    assert model.area_cm2 is None


def test_classifications_require_human_review_complete_ceap_and_valid_wifi():
    review = assessment_payload()["review"]
    with pytest.raises(ValidationError):
        CEAPClassification(clinical="C6", review=review)
    with pytest.raises(ValidationError):
        WIfIClassification(wound=4, ischemia=0, foot_infection=0, review=review)
    with pytest.raises(ValidationError):
        WIfIClassification(wound=True, ischemia=0, foot_infection=0, review=review)
    assert (
        CEAPClassification(
            clinical="C6", etiology=["Ep"], anatomy=["As"], pathophysiology=["Pr"], review=review
        ).clinical
        == "C6"
    )


def test_lpp_deep_stages_require_physical_examination_and_structure_record():
    review = assessment_payload()["review"]
    for stage in ("estagio_3", "estagio_4"):
        with pytest.raises(ValidationError):
            LPPClassification(stage=stage, review=review)
    with pytest.raises(ValidationError):
        LPPClassification(stage="estagio_4", depth_confirmed_in_person=True, review=review)
    assert (
        LPPClassification(
            stage="estagio_4", depth_confirmed_in_person=True, deep_structure_exposure=["tendao"], review=review
        ).stage
        == "estagio_4"
    )


def test_mucosal_device_injury_does_not_receive_lpp_stage():
    p = assessment_payload()
    p["wound_type"] = "lesao_por_pressao"
    p["device_association"] = dict(
        device_type="dispositivo sintético", contact_region="mucosa", mucosal_contact=True, review=p["review"]
    )
    p["classifications"] = dict(lpp=dict(stage="estagio_2", review=p["review"]))
    with pytest.raises(ValidationError):
        ClinicalAssessment.model_validate(p)


def principal_scope(role=Role.ENFERMEIRO):
    tenant, patient = uuid4(), uuid4()
    principal = Principal(
        user_id=uuid4(), tenant_id=tenant, role=role, authenticated=True, authorized_patient_ids={patient}
    )
    scope = ResourceScope(tenant_id=tenant, resource_id=uuid4(), patient_id=patient, data_class=DataClass.IDENTIFIABLE)
    return principal, scope


@pytest.mark.parametrize("role", list(Role))
def test_every_role_denied_unauthenticated_or_cross_tenant(role):
    p, r = principal_scope(role)
    for principal, resource in (
        (p.model_copy(update={"authenticated": False}), r),
        (p, r.model_copy(update={"tenant_id": uuid4()})),
    ):
        with pytest.raises(AccessDenied):
            authorize(principal, Action.READ_RECORD, resource)


@pytest.mark.parametrize("role", [Role.ENFERMEIRO, Role.MEDICO, Role.ESTOMATERAPEUTA])
def test_clinicians_only_authorized_patients_and_explicit_export(role):
    p, r = principal_scope(role)
    assert authorize(p, Action.READ_RECORD, r).allowed
    with pytest.raises(AccessDenied):
        authorize(p, Action.READ_RECORD, r.model_copy(update={"patient_id": uuid4()}))
    with pytest.raises(AccessDenied):
        authorize(p, Action.EXPORT, r)
    assert authorize(p, Action.EXPORT, r.model_copy(update={"export_authorized": True})).allowed


@pytest.mark.parametrize("role", [Role.PESQUISADOR, Role.ORIENTADOR, Role.DESENVOLVEDOR])
def test_researchers_only_approved_deidentified_or_public_data(role):
    p, r = principal_scope(role)
    with pytest.raises(AccessDenied):
        authorize(p, Action.READ_RESEARCH, r)
    anonymous = r.model_copy(update={"data_class": DataClass.DEIDENTIFIED, "patient_id": None})
    with pytest.raises(AccessDenied):
        authorize(p, Action.READ_RESEARCH, anonymous)
    assert authorize(p, Action.READ_RESEARCH, anonymous.model_copy(update={"research_approved": True})).allowed
    assert authorize(p, Action.RUN_EXPERIMENT, anonymous.model_copy(update={"data_class": DataClass.PUBLIC})).allowed


def test_admin_has_no_clinical_override_and_patient_module_is_disabled():
    admin, r = principal_scope(Role.ADMINISTRADOR)
    with pytest.raises(AccessDenied):
        authorize(admin, Action.RECORD_CARE_PLAN, r)
    assert authorize(
        admin, Action.MANAGE_USERS, r.model_copy(update={"patient_id": None, "data_class": DataClass.METADATA})
    ).allowed
    patient = Principal(
        user_id=uuid4(), tenant_id=r.tenant_id, role=Role.PACIENTE, authenticated=True, own_patient_id=r.patient_id
    )
    with pytest.raises(AccessDenied):
        authorize(patient, Action.READ_RECORD, r)
    assert authorize(patient, Action.READ_RECORD, r, policy=AccessPolicy(patient_portal_enabled=True)).allowed
    with pytest.raises(AccessDenied):
        authorize(
            patient,
            Action.READ_RECORD,
            r.model_copy(update={"patient_id": uuid4()}),
            policy=AccessPolicy(patient_portal_enabled=True),
        )


def event():
    return AuditEvent(
        actor_id=uuid4(),
        tenant_id=uuid4(),
        action=Action.READ_RECORD,
        outcome=AuditOutcome.COMPLETED,
        reason=AuditReason.OPERATION_COMPLETED,
        correlation_id=uuid4(),
    )


def test_audit_allow_and_deny_no_patient_payload_or_free_text(tmp_path):
    p, r = principal_scope()
    with AuditStore(tmp_path / "audit.sqlite", b"test-integrity-key-not-a-secret!!") as audit:
        authorize(p, Action.READ_RECORD, r, audit=audit)
        with pytest.raises(AccessDenied):
            authorize(p.model_copy(update={"authorized_patient_ids": frozenset()}), Action.READ_RECORD, r, audit=audit)
        entries = audit.events()
        assert [x.outcome for x in entries] == [AuditOutcome.ALLOWED, AuditOutcome.DENIED]
        assert str(r.patient_id) not in json.dumps([x.model_dump(mode="json") for x in entries])
        with pytest.raises(ValidationError):
            AuditEvent.model_validate(dict(event().model_dump(), prompt="clinical text", token="secret"))
        assert audit.verify_integrity()


def test_audit_detects_tampering_and_refuses_append(tmp_path):
    path = tmp_path / "audit.sqlite"
    with AuditStore(path, b"test-integrity-key-not-a-secret!!") as audit:
        audit.append(event())
        with sqlite3.connect(path) as external:
            external.execute("UPDATE heal_audit_events SET payload='{}' WHERE sequence=1")
        with pytest.raises(AuditIntegrityError):
            audit.verify_integrity()
        with pytest.raises(AuditIntegrityError):
            audit.append(event())


def test_audit_checkpoint_detects_tail_truncation_and_wrong_key(tmp_path):
    path = tmp_path / "audit.sqlite"
    key = b"test-integrity-key-not-a-secret!!"
    with AuditStore(path, key) as audit:
        audit.append(event())
        checkpoint = audit.checkpoint()
    with pytest.raises(AuditIntegrityError):
        AuditStore(path, b"wrong-test-key-32-bytes-or-more!!!")
    with sqlite3.connect(path) as external:
        external.execute("DELETE FROM heal_audit_events")
    with AuditStore(path, key) as audit:
        with pytest.raises(AuditIntegrityError):
            audit.verify_integrity(checkpoint)


def test_audit_concurrent_writers_are_transactional(tmp_path):
    with AuditStore(tmp_path / "audit.sqlite", b"test-integrity-key-not-a-secret!!") as audit:
        with ThreadPoolExecutor(max_workers=4) as executor:
            tuple(executor.map(lambda _: audit.append(event()), range(20)))
        assert len(audit.events()) == 20
        assert audit.verify_integrity()


def capture_protocol_payload():
    return dict(
        distance_cm=25,
        distance_source="medida_manual",
        angle_to_wound_plane_deg=90,
        angle_source="plano_medido_manualmente",
        scale_present=True,
        scale_next_to_wound=True,
        framing_complete=True,
        neutral_background=True,
        privacy_checked=True,
        consent_to_capture=True,
        identifying_exif_removed=True,
    )


def test_capture_protocol_is_persisted_and_old_import_remains_compatible():
    from heal_plus_redisus.src.sprint2_clinical_visual.guided_capture_validator import CaptureMeasurements as OldImport

    assert CaptureMeasurements is OldImport
    payload = assessment_payload()
    payload["images"][0].update(
        capture_protocol=capture_protocol_payload(),
        capture_status="aceito",
        scale_present=True,
        debridement_phase="pre_desbridamento",
    )
    model = ClinicalAssessment.model_validate(payload)
    restored = ClinicalAssessment.model_validate_json(model.model_dump_json())
    assert restored == model
    assert restored.images[0].capture_protocol.distance_cm == 25
    assert restored.images[0].debridement_phase == "pre_desbridamento"


def test_unknown_capture_measurements_remain_unknown_with_explicit_indeterminate_state():
    payload = assessment_payload()
    payload["images"][0].update(
        capture_protocol=dict(privacy_checked=True, consent_to_capture=True, identifying_exif_removed=True),
        capture_status="indeterminado",
    )
    image = ClinicalAssessment.model_validate(payload).images[0]
    assert image.capture_protocol.distance_cm is None
    assert image.capture_protocol.distance_source is None
    assert image.capture_protocol.angle_to_wound_plane_deg is None
    assert image.capture_status == "indeterminado"
    assert image.debridement_phase == "desconhecido"
    default_image = ClinicalAssessment.model_validate(assessment_payload()).images[0]
    assert default_image.capture_protocol is None and default_image.capture_status is None


@pytest.mark.parametrize("field", ["privacy_checked", "consent_to_capture", "identifying_exif_removed"])
@pytest.mark.parametrize("value", [False, None, "yes"])
def test_capture_record_requires_explicit_privacy_consent_and_metadata_confirmation(field, value):
    payload = assessment_payload()
    protocol = capture_protocol_payload()
    protocol[field] = value
    payload["images"][0].update(capture_protocol=protocol, capture_status="aceito", scale_present=True)
    with pytest.raises(ValidationError):
        ClinicalAssessment.model_validate(payload)


@pytest.mark.parametrize(
    "change",
    [
        {"scale_present": False},
        {"capture_status": None},
        {"capture_status": "rejeitado"},
        {"capture_protocol": None},
        {"debridement_phase": "inferido_automaticamente"},
    ],
)
def test_capture_record_rejects_inconsistent_scale_status_and_phase(change):
    payload = assessment_payload()
    payload["images"][0].update(
        capture_protocol=capture_protocol_payload(), capture_status="aceito", scale_present=True
    )
    payload["images"][0].update(change)
    with pytest.raises(ValidationError):
        ClinicalAssessment.model_validate(payload)


def test_missing_physical_measurements_cannot_be_recorded_as_capture_accepted():
    payload = assessment_payload()
    payload["images"][0].update(
        capture_protocol=dict(privacy_checked=True, consent_to_capture=True, identifying_exif_removed=True),
        capture_status="aceito",
    )
    with pytest.raises(ValidationError):
        ClinicalAssessment.model_validate(payload)
