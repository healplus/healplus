"""Read authorization precedes payload access, with no existence disclosure."""

import io
from uuid import uuid4

from PIL import Image
import pytest

from heal_plus_redisus.src.domain.clinical_models import ClinicalAssessment, PatientReference, PhotoConsent
from heal_plus_redisus.src.domain.rbac_audit import AccessDenied, AuditOutcome, AuditStore, Principal, Role
from heal_plus_redisus.src.service import SprintsService
from heal_plus_redisus.tests.test_domain import assessment_payload


@pytest.fixture
def records(tmp_path):
    payload = assessment_payload()
    principal = Principal(
        user_id=payload["professional_id"],
        tenant_id=uuid4(),
        role=Role.ENFERMEIRO,
        authenticated=True,
        authorized_patient_ids={payload["patient"]["patient_id"]},
    )
    audit = AuditStore(tmp_path / "audit.sqlite", b"synthetic-security-test-key-32bytes")
    service = SprintsService(tmp_path / "records.sqlite", audit)
    service.register_patient(principal, PatientReference.model_validate(payload["patient"]))
    service.register_wound(principal, payload["patient"]["patient_id"], payload["wound_id"])
    image = Image.new("RGB", (16, 16), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    image_record = service.upload_image(
        principal,
        patient_id=payload["patient"]["patient_id"],
        wound_id=payload["wound_id"],
        assessment_id=payload["assessment_id"],
        raw=buffer.getvalue(),
        content_type="image/png",
        consent=PhotoConsent.model_validate(payload["images"][0]["consent"]),
        privacy_reviewed=True,
        captured_at=payload["assessed_at"],
    )
    payload["images"] = [image_record.model_dump(mode="json")]
    assessment = ClinicalAssessment.model_validate(payload)
    service.save_assessment(principal, assessment)
    yield service, audit, principal, assessment, image_record
    service.close()
    audit.close()


@pytest.mark.parametrize("target", ["assessment", "image"])
@pytest.mark.parametrize(
    "mutation",
    [
        {"authenticated": False},
        {"role": Role.ADMINISTRADOR},
        {"role": Role.PESQUISADOR},
        {"authorized_patient_ids": frozenset()},
    ],
)
def test_authentication_and_role_gate_precedes_any_clinical_lookup(records, target, mutation):
    service, audit, principal, assessment, image = records
    caller = principal.model_copy(update=mutation)
    statements = []
    service.connection.set_trace_callback(statements.append)
    method, known = (
        (service.get_assessment, assessment.assessment_id)
        if target == "assessment"
        else (service.image_pixels, image.image_id)
    )
    failures = []
    for reference in (known, uuid4()):
        with pytest.raises(AccessDenied) as failure:
            method(caller, reference)
        failures.append(str(failure.value))
    assert failures[0] == failures[1]
    assert not any(statement.upper().startswith("SELECT") for statement in statements)
    assert [event.outcome for event in audit.events()[-2:]] == [AuditOutcome.DENIED] * 2


@pytest.mark.parametrize("target", ["assessment", "image"])
@pytest.mark.parametrize("mutation", ["other_patient", "other_tenant"])
def test_user_and_tenant_swap_never_reads_payload_or_discloses_existence(records, target, mutation):
    service, audit, principal, assessment, image = records
    caller = principal.model_copy(
        update={
            "user_id": uuid4(),
            **(
                {"authorized_patient_ids": frozenset({uuid4()})}
                if mutation == "other_patient"
                else {"tenant_id": uuid4()}
            ),
        }
    )
    statements = []
    service.connection.set_trace_callback(statements.append)
    method, known = (
        (service.get_assessment, assessment.assessment_id)
        if target == "assessment"
        else (service.image_pixels, image.image_id)
    )
    for reference in (known, uuid4()):
        with pytest.raises(AccessDenied):
            method(caller, reference)
    assert not any("SELECT record" in statement or "SELECT content" in statement for statement in statements)
    assert [event.outcome for event in audit.events()[-2:]] == [AuditOutcome.DENIED] * 2


def test_authorized_unknown_lookup_is_uniform_and_audited(records):
    service, audit, principal, *_ = records
    initial = len(audit.events())
    with pytest.raises(AccessDenied):
        service.get_assessment(principal, uuid4())
    with pytest.raises(AccessDenied):
        service.image_pixels(principal, uuid4())
    assert len(audit.events()) == initial + 2
    assert all(event.outcome == AuditOutcome.DENIED for event in audit.events()[-2:])


def test_authorized_lookup_still_returns_record_and_pixels(records):
    service, _, principal, assessment, image = records
    assert service.get_assessment(principal, assessment.assessment_id) == assessment
    assert service.image_pixels(principal, image.image_id).shape == (16, 16, 3)


def test_patient_registration_checks_authentication_before_existence(records):
    service, _, principal, assessment, _ = records
    statements = []
    service.connection.set_trace_callback(statements.append)
    caller = principal.model_copy(update={"authenticated": False})
    for patient in (assessment.patient, PatientReference(patient_id=uuid4(), pseudonym="pt_synthetic02")):
        with pytest.raises(AccessDenied):
            service.register_patient(caller, patient)
    assert not any(statement.upper().startswith("SELECT") for statement in statements)


@pytest.mark.parametrize("nested", ["care_plan", "ceap", "device_association", "perfusion", "neuropathy"])
@pytest.mark.parametrize("false_claim", ["reviewer_id", "role"])
def test_nested_review_must_be_attested_by_authenticated_professional(records, nested, false_claim):
    service, audit, principal, assessment, _ = records
    payload = assessment.model_dump(mode="json")
    review = dict(payload["review"])
    review[false_claim] = str(uuid4()) if false_claim == "reviewer_id" else "Médico"
    if nested == "care_plan":
        payload["care_plan"]["review"] = review
    elif nested == "ceap":
        payload["classifications"] = dict(
            ceap=dict(clinical="C6", etiology=["Ep"], anatomy=["As"], pathophysiology=["Pr"], review=review)
        )
    elif nested == "device_association":
        payload[nested] = dict(
            device_type="dispositivo sintético", contact_region="perna", mucosal_contact=False, review=review
        )
    elif nested == "perfusion":
        payload[nested] = dict(observations="Registro sintético.", review=review)
    else:
        payload[nested] = dict(
            protective_sensation="nao_avaliada",
            examination_method="Não realizado.",
            observations="Registro sintético.",
            review=review,
        )
    with pytest.raises(PermissionError):
        service.save_assessment(principal, ClinicalAssessment.model_validate(payload))
    assert service.get_assessment(principal, assessment.assessment_id) == assessment
    assert AuditOutcome.FAILED in [event.outcome for event in audit.events()[-4:]]


def test_nurse_without_care_assignment_creates_idempotently_without_lookup_or_overwrite(records):
    service, audit, principal, assessment, _ = records
    creator = principal.model_copy(update={"user_id": uuid4(), "authorized_patient_ids": frozenset()})
    replacement = PatientReference(patient_id=assessment.patient.patient_id, pseudonym="pt_no_overwrite")
    new_patient = PatientReference(patient_id=uuid4(), pseudonym="pt_new_synthetic")
    statements = []
    service.connection.set_trace_callback(statements.append)
    service.register_patient(creator, replacement)
    service.register_patient(creator, new_patient)
    service.connection.set_trace_callback(None)
    assert not any(statement.upper().startswith("SELECT") for statement in statements)
    assert service.get_patient(principal, assessment.patient.patient_id) == assessment.patient
    stored = service.connection.execute(
        "SELECT record FROM sprint_patients WHERE tenant_id=? AND patient_id=?",
        (str(principal.tenant_id), str(new_patient.patient_id)),
    ).fetchone()
    assert PatientReference.model_validate_json(stored[0]) == new_patient
