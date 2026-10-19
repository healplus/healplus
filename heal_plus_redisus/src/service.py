"""Authorized persistent workflow for the sprint modules, independent of a web UI.

Construct Principal only from a verified backend identity and authoritative care
assignments. This in-process API deliberately does not implement a second login
server or expose an unauthenticated HTTP route.
"""

from __future__ import annotations

import hashlib
import io
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

import numpy as np
from PIL import Image

from .domain.clinical_models import ClinicalAssessment, ImageRecord, PatientReference, PhotoConsent
from .domain.capture_models import CaptureMeasurements
from .domain.rbac_audit import (
    AccessDenied,
    Action,
    AuditEvent,
    AuditOutcome,
    AuditReason,
    AuditStore,
    DataClass,
    Principal,
    ResourceScope,
    authorize,
    decide_access,
)
from .interoperability.fhir_exporter import SprintsFHIRExporter
from .privacy import sanitize_upload
from .safety import ASSISTIVE_DISCLAIMER


class SprintsService:
    def __init__(self, database: str | Path, audit: AuditStore):
        self.audit = audit
        self.connection = sqlite3.connect(str(database))
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA synchronous=FULL")
        migration = Path(__file__).resolve().parents[1] / "config" / "migrations" / "001_records.sql"
        self.connection.executescript(migration.read_text(encoding="utf-8"))
        if {row[0] for row in self.connection.execute("SELECT version FROM sprint_schema")} != {1}:
            self.connection.close()
            raise RuntimeError("Versão do banco não suportada.")

    def close(self) -> None:
        self.connection.close()

    @contextmanager
    def _operation(self, principal: Principal, action: Action, scope: ResourceScope):
        correlation = uuid4()
        authorize(principal, action, scope, audit=self.audit, correlation_id=correlation)
        try:
            yield
        except Exception:
            self.audit.append(
                AuditEvent(
                    actor_id=principal.user_id,
                    tenant_id=principal.tenant_id,
                    action=action,
                    outcome=AuditOutcome.FAILED,
                    reason=AuditReason.OPERATION_FAILED,
                    correlation_id=correlation,
                )
            )
            raise
        else:
            self.audit.append(
                AuditEvent(
                    actor_id=principal.user_id,
                    tenant_id=principal.tenant_id,
                    action=action,
                    outcome=AuditOutcome.COMPLETED,
                    reason=AuditReason.OPERATION_COMPLETED,
                    correlation_id=correlation,
                )
            )

    @staticmethod
    def _scope(principal: Principal, patient_id: UUID | None, resource_id: UUID, *, export=False) -> ResourceScope:
        return ResourceScope(
            tenant_id=principal.tenant_id,
            patient_id=patient_id,
            resource_id=resource_id,
            data_class=DataClass.IDENTIFIABLE,
            export_authorized=export,
        )

    def register_patient(self, principal: Principal, patient: PatientReference) -> None:
        patient = PatientReference.model_validate(patient.model_dump(mode="json"))
        create_scope = ResourceScope(
            tenant_id=principal.tenant_id, resource_id=patient.patient_id, data_class=DataClass.METADATA
        )
        update_scope = self._scope(principal, patient.patient_id, patient.patient_id)
        # Establish an allowed operation before consulting even record existence.
        if not (
            decide_access(principal, Action.REGISTER_PATIENT, create_scope).allowed
            or decide_access(principal, Action.WRITE_RECORD, update_scope).allowed
        ):
            authorize(principal, Action.WRITE_RECORD, update_scope, audit=self.audit)
        if patient.patient_id not in principal.authorized_patient_ids:
            with self._operation(principal, Action.REGISTER_PATIENT, create_scope), self.connection:
                # A creator without a care assignment cannot probe existing IDs.
                self.connection.execute(
                    "INSERT OR IGNORE INTO sprint_patients VALUES(?,?,?)",
                    (str(principal.tenant_id), str(patient.patient_id), patient.model_dump_json()),
                )
            return
        existing = self.connection.execute(
            "SELECT 1 FROM sprint_patients WHERE tenant_id=? AND patient_id=?",
            (str(principal.tenant_id), str(patient.patient_id)),
        ).fetchone()
        if existing:
            scope = self._scope(principal, patient.patient_id, patient.patient_id)
            action = Action.WRITE_RECORD
        else:
            scope = ResourceScope(
                tenant_id=principal.tenant_id, resource_id=patient.patient_id, data_class=DataClass.METADATA
            )
            action = Action.REGISTER_PATIENT
        with self._operation(principal, action, scope), self.connection:
            self.connection.execute(
                "INSERT INTO sprint_patients VALUES(?,?,?) ON CONFLICT(tenant_id,patient_id) DO UPDATE SET record=excluded.record",
                (str(principal.tenant_id), str(patient.patient_id), patient.model_dump_json()),
            )

    def get_patient(self, principal: Principal, patient_id: UUID) -> PatientReference:
        with self._operation(principal, Action.READ_RECORD, self._scope(principal, patient_id, patient_id)):
            row = self.connection.execute(
                "SELECT record FROM sprint_patients WHERE tenant_id=? AND patient_id=?",
                (str(principal.tenant_id), str(patient_id)),
            ).fetchone()
            if row is None:
                raise LookupError("Registro indisponível.")
            return PatientReference.model_validate_json(row[0])

    def register_wound(self, principal: Principal, patient_id: UUID, wound_id: UUID) -> None:
        with (
            self._operation(principal, Action.WRITE_RECORD, self._scope(principal, patient_id, wound_id)),
            self.connection,
        ):
            self._require_wound_or_patient(principal, patient_id)
            existing = self.connection.execute(
                "SELECT patient_id FROM sprint_wounds WHERE tenant_id=? AND wound_id=?",
                (str(principal.tenant_id), str(wound_id)),
            ).fetchone()
            if existing and existing[0] != str(patient_id):
                raise ValueError("Vínculo de ferida inconsistente.")
            self.connection.execute(
                "INSERT OR IGNORE INTO sprint_wounds VALUES(?,?,?)",
                (str(principal.tenant_id), str(wound_id), str(patient_id)),
            )

    def _require_wound_or_patient(self, principal: Principal, patient_id: UUID, wound_id: UUID | None = None):
        if wound_id is None:
            row = self.connection.execute(
                "SELECT 1 FROM sprint_patients WHERE tenant_id=? AND patient_id=?",
                (str(principal.tenant_id), str(patient_id)),
            ).fetchone()
        else:
            row = self.connection.execute(
                "SELECT 1 FROM sprint_wounds WHERE tenant_id=? AND patient_id=? AND wound_id=?",
                (str(principal.tenant_id), str(patient_id), str(wound_id)),
            ).fetchone()
        if row is None:
            raise LookupError("Registro indisponível ou vínculo inconsistente.")

    def upload_image(
        self,
        principal: Principal,
        *,
        patient_id: UUID,
        wound_id: UUID,
        assessment_id: UUID,
        raw: bytes,
        content_type: str,
        consent: PhotoConsent,
        privacy_reviewed: bool,
        captured_at: datetime,
        purpose: Literal["acompanhamento_assistencial", "pesquisa_aprovada"] = "acompanhamento_assistencial",
        scale_present: bool = False,
        capture_measurements: CaptureMeasurements | None = None,
        capture_perilesional_mask: np.ndarray | None = None,
        debridement_phase: Literal[
            "pre_desbridamento", "pos_desbridamento", "nao_aplicavel", "desconhecido"
        ] = "desconhecido",
    ) -> ImageRecord:
        scope = self._scope(principal, patient_id, assessment_id)
        with self._operation(principal, Action.UPLOAD_IMAGE, scope):
            self._require_wound_or_patient(principal, patient_id, wound_id)
            # Revalidate models at every trust boundary; model_copy may bypass validators.
            consent = PhotoConsent.model_validate(consent.model_dump(mode="json"))
            clean = sanitize_upload(
                raw, content_type, consent=consent.capture_authorized, privacy_reviewed=privacy_reviewed
            )
            protocol = None
            capture_status = None
            if capture_measurements is not None:
                from .sprint2_clinical_visual.guided_capture_validator import GuidedCaptureValidator

                data = capture_measurements.model_dump(mode="json")
                data["identifying_exif_removed"] = True
                protocol = CaptureMeasurements.model_validate(data)
                validation = GuidedCaptureValidator().validate(
                    clean.rgb, protocol, perilesional_mask=capture_perilesional_mask
                )
                if validation.status == "rejeitado":
                    raise ValueError(
                        "A captura não atende ao protocolo técnico. Revise foco, iluminação, medidas e confirmações antes de reenviar."
                    )
                capture_status = validation.status
                scale_present = protocol.scale_present is True
            record = ImageRecord(
                image_id=uuid4(),
                patient_id=patient_id,
                wound_id=wound_id,
                assessment_id=assessment_id,
                captured_at=captured_at,
                captured_by=principal.user_id,
                purpose=purpose,
                consent=consent,
                content_sha256=clean.sha256,
                exif_removed=True,
                scale_present=scale_present,
                capture_protocol=protocol,
                capture_status=capture_status,
                debridement_phase=debridement_phase,
            )
            with self.connection:
                self.connection.execute(
                    "INSERT INTO sprint_images VALUES(?,?,?,?,?,?,?)",
                    (
                        str(principal.tenant_id),
                        str(record.image_id),
                        str(patient_id),
                        str(wound_id),
                        str(assessment_id),
                        record.model_dump_json(),
                        clean.content,
                    ),
                )
            return record

    def save_assessment(self, principal: Principal, assessment: ClinicalAssessment) -> int:
        assessment = ClinicalAssessment.model_validate(assessment.model_dump(mode="json"))
        scope = self._scope(principal, assessment.patient.patient_id, assessment.assessment_id)
        with self._operation(principal, Action.WRITE_RECORD, scope):
            if assessment.professional_id != principal.user_id or assessment.review.role.value != principal.role.value:
                raise PermissionError(
                    "O responsável pelo registro deve corresponder à identidade profissional autenticada."
                )
            reviews = [assessment.care_plan.review]
            for value in (assessment.device_association, assessment.perfusion, assessment.neuropathy):
                if value is not None:
                    reviews.append(value.review)
            if assessment.classifications:
                for classification in (
                    assessment.classifications.ceap,
                    assessment.classifications.wifi,
                    assessment.classifications.fontaine,
                    assessment.classifications.lpp,
                ):
                    if classification is not None:
                        reviews.append(classification.review)
            if any(
                review.reviewer_id != principal.user_id or review.role.value != principal.role.value
                for review in reviews
            ):
                raise PermissionError("As revisões deste fluxo devem ser atestadas pelo profissional autenticado.")
            self._require_wound_or_patient(principal, assessment.patient.patient_id, assessment.wound_id)
            patient_row = self.connection.execute(
                "SELECT record FROM sprint_patients WHERE tenant_id=? AND patient_id=?",
                (str(principal.tenant_id), str(assessment.patient.patient_id)),
            ).fetchone()
            if PatientReference.model_validate_json(patient_row[0]) != assessment.patient:
                raise ValueError("O paciente informado não corresponde ao cadastro autorizado.")
            for image in assessment.images:
                row = self.connection.execute(
                    "SELECT record,content FROM sprint_images WHERE tenant_id=? AND image_id=? AND patient_id=? AND wound_id=? AND assessment_id=?",
                    (
                        str(principal.tenant_id),
                        str(image.image_id),
                        str(assessment.patient.patient_id),
                        str(assessment.wound_id),
                        str(assessment.assessment_id),
                    ),
                ).fetchone()
                if row is None or ImageRecord.model_validate_json(row[0]) != image:
                    raise ValueError("A avaliação deve usar imagens inseridas e autorizadas neste serviço.")
                if hashlib.sha256(row[1]).hexdigest() != image.content_sha256:
                    raise ValueError("Falha de integridade da imagem.")
            previous_id = assessment.temporal_evolution.previous_assessment_id
            if previous_id:
                previous = self._load_assessment(principal, previous_id)
                if (previous.patient.patient_id, previous.wound_id) != (
                    assessment.patient.patient_id,
                    assessment.wound_id,
                ) or previous.assessed_at >= assessment.assessed_at:
                    raise ValueError("O registro anterior deve ser da mesma ferida e anterior à avaliação atual.")
            with self.connection:
                existing = self.connection.execute(
                    "SELECT patient_id,wound_id,revision FROM sprint_assessments WHERE tenant_id=? AND assessment_id=?",
                    (str(principal.tenant_id), str(assessment.assessment_id)),
                ).fetchone()
                if existing and tuple(existing[:2]) != (str(assessment.patient.patient_id), str(assessment.wound_id)):
                    raise ValueError("Não é permitido trocar o vínculo de uma avaliação existente.")
                revision = existing[2] + 1 if existing else 1
                values = (
                    str(principal.tenant_id),
                    str(assessment.assessment_id),
                    str(assessment.patient.patient_id),
                    str(assessment.wound_id),
                    revision,
                    assessment.model_dump_json(),
                )
                self.connection.execute(
                    "INSERT INTO sprint_assessments VALUES(?,?,?,?,?,?) ON CONFLICT(tenant_id,assessment_id) DO UPDATE SET revision=excluded.revision,record=excluded.record",
                    values,
                )
                self.connection.execute(
                    "INSERT INTO sprint_assessment_versions VALUES(?,?,?,?)",
                    (values[0], values[1], revision, values[5]),
                )
                self.connection.execute("DELETE FROM sprint_analyses WHERE tenant_id=? AND assessment_id=?", values[:2])
            return revision

    def _load_assessment(self, principal: Principal, assessment_id: UUID) -> ClinicalAssessment:
        patient_id = self._lookup_authorized_patient(principal, "sprint_assessments", "assessment_id", assessment_id)
        with self._operation(principal, Action.READ_RECORD, self._scope(principal, patient_id, assessment_id)):
            row = self.connection.execute(
                "SELECT record FROM sprint_assessments WHERE tenant_id=? AND assessment_id=? AND patient_id=?",
                (str(principal.tenant_id), str(assessment_id), str(patient_id)),
            ).fetchone()
            if row is None:
                raise AccessDenied("Acesso não autorizado para esta operação.")
            assessment = ClinicalAssessment.model_validate_json(row[0])
            if assessment.patient.patient_id != patient_id:
                raise ValueError("Vínculo persistido inconsistente.")
            return assessment

    def _lookup_authorized_patient(self, principal: Principal, table: str, id_column: str, resource_id: UUID) -> UUID:
        # Table/column pairs are internal constants, not request parameters.
        if (table, id_column) not in {("sprint_assessments", "assessment_id"), ("sprint_images", "image_id")}:
            raise ValueError("Recurso indisponível.")
        patient_ids = tuple(principal.authorized_patient_ids)
        candidate_scope = self._scope(principal, patient_ids[0] if patient_ids else None, resource_id)
        if not decide_access(principal, Action.READ_RECORD, candidate_scope).allowed:
            authorize(principal, Action.READ_RECORD, candidate_scope, audit=self.audit)
        placeholders = ",".join("?" for _ in patient_ids)
        row = self.connection.execute(
            f"SELECT patient_id FROM {table} WHERE tenant_id=? AND {id_column}=? AND patient_id IN ({placeholders})",
            (str(principal.tenant_id), str(resource_id), *(str(patient_id) for patient_id in patient_ids)),
        ).fetchone()
        if row is None:
            # Unknown, another patient's and another tenant's IDs have one public
            # failure, and none causes a payload/blob to be read or deserialized.
            self.audit.append(
                AuditEvent(
                    actor_id=principal.user_id,
                    tenant_id=principal.tenant_id,
                    action=Action.READ_RECORD,
                    outcome=AuditOutcome.DENIED,
                    reason=AuditReason.PATIENT_LINK_REQUIRED,
                    correlation_id=uuid4(),
                )
            )
            raise AccessDenied("Acesso não autorizado para esta operação.")
        return UUID(row[0])

    def get_assessment(self, principal: Principal, assessment_id: UUID) -> ClinicalAssessment:
        return self._load_assessment(principal, assessment_id)

    def history(self, principal: Principal, patient_id: UUID, wound_id: UUID) -> tuple[ClinicalAssessment, ...]:
        with self._operation(principal, Action.READ_RECORD, self._scope(principal, patient_id, wound_id)):
            self._require_wound_or_patient(principal, patient_id, wound_id)
            rows = self.connection.execute(
                "SELECT record FROM sprint_assessments WHERE tenant_id=? AND patient_id=? AND wound_id=?",
                (str(principal.tenant_id), str(patient_id), str(wound_id)),
            ).fetchall()
            return tuple(
                sorted(
                    (ClinicalAssessment.model_validate_json(row[0]) for row in rows),
                    key=lambda record: record.assessed_at,
                )
            )

    def image_pixels(self, principal: Principal, image_id: UUID) -> np.ndarray:
        patient_id = self._lookup_authorized_patient(principal, "sprint_images", "image_id", image_id)
        with self._operation(principal, Action.READ_RECORD, self._scope(principal, patient_id, image_id)):
            row = self.connection.execute(
                "SELECT content,record FROM sprint_images WHERE tenant_id=? AND image_id=? AND patient_id=?",
                (str(principal.tenant_id), str(image_id), str(patient_id)),
            ).fetchone()
            if row is None:
                raise AccessDenied("Acesso não autorizado para esta operação.")
            record = ImageRecord.model_validate_json(row[1])
            if record.patient_id != patient_id:
                raise ValueError("Vínculo persistido inconsistente.")
            if hashlib.sha256(row[0]).hexdigest() != record.content_sha256:
                raise ValueError("Falha de integridade da imagem.")
            with Image.open(io.BytesIO(row[0])) as image:
                return np.array(image.convert("RGB"))

    def analyze(
        self, principal: Principal, assessment_id: UUID, image_id: UUID, *, rois, segmenter, bed_masks=None
    ) -> dict:
        assessment = self._load_assessment(principal, assessment_id)
        if image_id not in {image.image_id for image in assessment.images}:
            raise ValueError("A imagem deve pertencer à avaliação selecionada.")
        with self._operation(
            principal, Action.MARK_ROI, self._scope(principal, assessment.patient.patient_id, assessment_id)
        ):
            from .sprint1_pipeline.roi_handler import ROIHandler

            current = self.connection.execute(
                "SELECT revision,record FROM sprint_assessments WHERE tenant_id=? AND assessment_id=?",
                (str(principal.tenant_id), str(assessment_id)),
            ).fetchone()
            if ClinicalAssessment.model_validate_json(current[1]) != assessment:
                raise ValueError("A avaliação foi atualizada. Recarregue o registro antes da análise.")
            revision = current[0]
            rgb = self.image_pixels(principal, image_id)
            rois = ROIHandler().validate(rgb, rois)
            mapping = {
                "lesao_por_pressao": "pressure",
                "ulcera_venosa": "venous",
                "ulcera_arterial": "arterial",
                "pe_diabetico": "diabetic",
                "nao_determinada": "unknown",
            }
            context: dict[str, Any] = {"etiology": mapping.get(assessment.wound_type.value, "other")}
            selected_image = next(image for image in assessment.images if image.image_id == image_id)
            context["recent_debridement"] = selected_image.debridement_phase == "pos_desbridamento"
            results = [
                segmenter.segment(rgb, roi, context=context, bed_mask=(bed_masks or {}).get(roi.id)) for roi in rois
            ]
            summary = {
                "assessment_id": str(assessment_id),
                "image_id": str(image_id),
                "rois": [result.to_dict() for result in results],
                "roi_records": [{"id": roi.id, "bbox": list(roi.bbox)} for roi in rois],
                "model_version": getattr(getattr(segmenter, "backend", None), "model_version", "unavailable"),
                "checkpoint_sha256": getattr(getattr(segmenter, "backend", None), "checkpoint_sha256", None),
                "status": "assistive_experimental",
                "disclaimer": ASSISTIVE_DISCLAIMER,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            with self.connection:
                self.connection.execute("BEGIN IMMEDIATE")
                latest_revision = self.connection.execute(
                    "SELECT revision FROM sprint_assessments WHERE tenant_id=? AND assessment_id=?",
                    (str(principal.tenant_id), str(assessment_id)),
                ).fetchone()[0]
                if latest_revision != revision:
                    raise ValueError("A avaliação mudou durante a análise. Recarregue o registro e execute novamente.")
                self.connection.execute(
                    "INSERT INTO sprint_analyses VALUES(?,?,?,?,?) ON CONFLICT(tenant_id,assessment_id,image_id) DO UPDATE SET assessment_revision=excluded.assessment_revision,summary=excluded.summary",
                    (
                        str(principal.tenant_id),
                        str(assessment_id),
                        str(image_id),
                        revision,
                        json.dumps(summary, ensure_ascii=False, allow_nan=False),
                    ),
                )
            return summary

    def export_fhir(
        self,
        principal: Principal,
        assessment_id: UUID,
        *,
        confirmed: bool,
        research: bool = False,
        bundle_type: Literal["collection", "transaction"] = "collection",
    ) -> dict:
        assessment = self._load_assessment(principal, assessment_id)
        scope = self._scope(principal, assessment.patient.patient_id, assessment_id, export=confirmed is True)
        with self._operation(principal, Action.EXPORT, scope), self.connection:
            self.connection.execute("BEGIN")
            current = self.connection.execute(
                "SELECT revision,record FROM sprint_assessments WHERE tenant_id=? AND assessment_id=? AND patient_id=?",
                (str(principal.tenant_id), str(assessment_id), str(assessment.patient.patient_id)),
            ).fetchone()
            if current is None:
                raise AccessDenied("Acesso não autorizado para esta operação.")
            revision = current[0]
            assessment = ClinicalAssessment.model_validate_json(current[1])
            rows = self.connection.execute(
                "SELECT summary FROM sprint_analyses WHERE tenant_id=? AND assessment_id=? AND assessment_revision=?",
                (str(principal.tenant_id), str(assessment_id), revision),
            ).fetchall()
            summaries = [json.loads(row[0]) for row in rows]
            # Components identify image+ROI to keep multiple photographs unambiguous.
            results = []
            roi_records: list[dict[str, Any]] = []
            for summary in summaries:
                for result in summary["rois"]:
                    result["roi_id"] = summary["image_id"] + ":" + result["roi_id"]
                    results.append(result)
                roi_records.extend({**roi, "image_id": summary["image_id"]} for roi in summary["roi_records"])
            versions = sorted({summary["model_version"] for summary in summaries})
            analysis = (
                {"rois": results, "status": "assistive_experimental", "model_version": ",".join(versions)}
                if results
                else None
            )
            return SprintsFHIRExporter().export(
                assessment,
                analysis=analysis,
                roi_records=roi_records,
                research=research,
                bundle_type=bundle_type,
                assessment_revision=revision,
            )
