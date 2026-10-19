"""FHIR R4 4.0.1 bundles, validated offline against the repository's HL7 schema.

Terminology without an institutionally reviewed mapping uses local codes. No
RNDS profile conformance, clinical validation or external publication is claimed.
Authorization is enforced by SprintsService before invoking this internal mapper.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
import math
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence
from uuid import UUID, uuid4, uuid5

from jsonschema import Draft6Validator

from ..domain.clinical_models import ClinicalAssessment
from ..safety import ASSISTIVE_DISCLAIMER, TISSUE_CLASSES

LOCAL = "https://heal.redisus.org.br/fhir/CodeSystem/sprints-research"
EXTENSIONS = "https://heal.redisus.org.br/fhir/StructureDefinition/"
NAMESPACE = UUID("7d8b3f3c-2323-4166-aec3-d28f7fd30192")
KINDS = (
    "Patient",
    "Practitioner",
    "Condition",
    "Media",
    "Observation",
    "DiagnosticReport",
    "CarePlan",
    "Procedure",
    "Device",
    "DeviceUseStatement",
    "Provenance",
)


@lru_cache(maxsize=1)
def _schema() -> dict:
    source = Path(__file__).resolve().parents[2] / "config" / "fhir-export.schema.json"
    schema = json.loads(source.read_text(encoding="utf-8"))
    return schema


def validate_bundle(bundle: dict) -> None:
    """Structure + closed internal references; errors never echo clinical inputs."""
    try:
        json.dumps(bundle, allow_nan=False)
        schema = {**_schema(), "$ref": "#/definitions/Bundle"}
        schema.pop("oneOf", None)
        if next(Draft6Validator(schema).iter_errors(bundle), None) is not None:
            raise ValueError
        if bundle.get("type") not in {"collection", "transaction"}:
            raise ValueError
        entries = bundle.get("entry", [])
        refs = {entry["fullUrl"] for entry in entries}
        if not entries or len(refs) != len(entries):
            raise ValueError
        identities = set()
        for entry in entries:
            resource = entry["resource"]
            if resource.get("resourceType") not in KINDS:
                raise ValueError
            identity = (resource["resourceType"], resource["id"])
            if identity in identities:
                raise ValueError
            identities.add(identity)
            if bundle["type"] == "transaction":
                if entry.get("request") != {"method": "PUT", "url": "/".join(identity)}:
                    raise ValueError
            elif "request" in entry or "response" in entry:
                raise ValueError

        def check(value):
            if isinstance(value, dict):
                if "reference" in value and value["reference"] not in refs:
                    raise ValueError
                for child in value.values():
                    check(child)
            elif isinstance(value, list):
                for child in value:
                    check(child)

        check(bundle)
    except (ValueError, KeyError, TypeError):
        raise ValueError("Bundle inválido para o contrato local e a estrutura HL7 FHIR R4 4.0.1.") from None


def _concept(code: str, text: str | None = None) -> dict:
    return {"coding": [{"system": LOCAL, "code": code}], "text": text or code}


def _quantity(name: str, value: float, unit: str) -> dict:
    return {
        "code": _concept(name),
        "valueQuantity": {"value": float(value), "unit": unit, "system": "http://unitsofmeasure.org", "code": unit},
    }


class SprintsFHIRExporter:
    def export(
        self,
        assessment: ClinicalAssessment,
        *,
        analysis: Mapping[str, Any] | None = None,
        roi_records: Sequence[Mapping[str, Any]] = (),
        bundle_type: Literal["collection", "transaction"] = "collection",
        research: bool = False,
        manifest_sha256: str | None = None,
        assessment_revision: int | None = None,
    ) -> dict:
        """Minimized patient; research export additionally omits all free text.

        ``analysis`` is the service's measured, provenance-bound summary. It is
        never interpreted as a diagnosis and its five-class denominator is explicit.
        """
        assessment = ClinicalAssessment.model_validate(assessment.model_dump(mode="json"))
        if bundle_type not in {"collection", "transaction"}:
            raise ValueError("Escolha collection ou transaction.")
        if research and not all(image.consent.research_use_authorized for image in assessment.images):
            raise PermissionError("A exportação de pesquisa exige consentimento específico e governança.")
        resources: list[dict] = []
        namespace = uuid4() if research else NAMESPACE
        exported_at = datetime.now(timezone.utc).isoformat()

        def identity(kind: str, source: object) -> str:
            return str(uuid5(namespace, f"{kind}:{source}"))

        def reference(kind: str, source: object) -> dict:
            return {"reference": f"urn:uuid:{identity(kind, source)}"}

        def add(kind: str, source: object, **fields):
            resource = {"resourceType": kind, "id": identity(kind, source), **fields}
            resources.append(resource)
            return resource

        patient_id = assessment.patient.patient_id
        patient_ref = reference("Patient", patient_id)
        wound_ref = reference("Condition", assessment.wound_id)
        practitioner_ref = reference("Practitioner", assessment.professional_id)
        observation_ref = reference("Observation", assessment.assessment_id)
        date = assessment.assessed_at.isoformat()
        # No name, birth date, CPF, CNS, address, telecom or identifying filenames.
        patient_alias = (
            "pt_" + identity("Patient", patient_id).replace("-", "") if research else assessment.patient.pseudonym
        )
        add("Patient", patient_id, identifier=[{"system": "urn:healplus:pseudonym", "value": patient_alias}])
        add("Practitioner", assessment.professional_id, active=True)
        condition = add(
            "Condition",
            assessment.wound_id,
            subject=patient_ref,
            clinicalStatus={
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]
            },
            verificationStatus={
                "coding": [
                    {"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "provisional"}
                ]
            },
            code=_concept(assessment.wound_type.value, "Tipo informado por profissional responsável"),
            recordedDate=date,
            recorder=practitioner_ref,
        )
        if not research:
            condition["bodySite"] = [{"text": assessment.anatomical_location.region}]
            condition["note"] = [{"text": assessment.history.context}, {"text": ASSISTIVE_DISCLAIMER}]
        else:
            condition.pop("recordedDate", None)

        media_refs = []
        for image in assessment.images:
            media_ref = reference("Media", image.image_id)
            media_refs.append(media_ref)
            extensions: list[dict[str, Any]] = [
                {"url": EXTENSIONS + "content-sha256", "valueString": image.content_sha256},
                {"url": EXTENSIONS + "metadata-removed", "valueBoolean": image.exif_removed},
                {"url": EXTENSIONS + "scale-confirmed", "valueBoolean": image.scale_present},
                {"url": EXTENSIONS + "debridement-phase", "valueCode": image.debridement_phase},
            ]
            if image.capture_protocol is not None:
                extensions.append(
                    {
                        "url": EXTENSIONS + "capture-protocol",
                        "valueString": image.capture_protocol.model_dump_json(exclude_none=True),
                    }
                )
                extensions.append({"url": EXTENSIONS + "capture-status", "valueCode": image.capture_status})
            matching_rois = [roi for roi in roi_records if roi.get("image_id") in {None, str(image.image_id)}]
            if matching_rois:
                values = [
                    {"id": identity("Observation", roi["id"]) if research else roi["id"], "bbox": list(roi["bbox"])}
                    for roi in matching_rois
                ]
                extensions.append(
                    {
                        "url": EXTENSIONS + "roi-coordinates",
                        "valueString": json.dumps(values, ensure_ascii=False, allow_nan=False),
                    }
                )
            media = add(
                "Media",
                image.image_id,
                status="completed",
                type={"coding": [{"system": "http://terminology.hl7.org/CodeSystem/media-type", "code": "image"}]},
                subject=patient_ref,
                createdDateTime=image.captured_at.isoformat(),
                reasonCode=[_concept(image.purpose)],
                content={
                    "contentType": "image/png",
                    "title": "Fotografia com metadados removidos; acesso ao conteúdo controlado",
                },
                extension=extensions,
                note=[{"text": ASSISTIVE_DISCLAIMER}],
            )
            if research:
                media.pop("createdDateTime", None)
                media["extension"] = [
                    extension for extension in extensions if extension["url"] != EXTENSIONS + "content-sha256"
                ]

        components = []
        dimensions = assessment.dimensions
        for key, unit in (("length_cm", "cm"), ("width_cm", "cm"), ("depth_cm", "cm"), ("area_cm2", "cm2")):
            value = getattr(dimensions, key)
            if value is not None:
                components.append(_quantity(key, value, unit))
        if assessment.tissue_composition is not None:
            for tissue, value in assessment.tissue_composition.model_dump().items():
                components.append(_quantity("professional-" + tissue, value, "%"))
        if assessment.pain is not None:
            components.append(_quantity("pain-0-10", assessment.pain.intensity, "1"))
        if assessment.perfusion is not None:
            for name, unit in (
                ("ankle_brachial_index", "1"),
                ("ankle_pressure_mmhg", "mm[Hg]"),
                ("toe_pressure_mmhg", "mm[Hg]"),
                ("transcutaneous_oxygen_mmhg", "mm[Hg]"),
            ):
                value = getattr(assessment.perfusion, name)
                if value is not None:
                    components.append(_quantity("professional-perfusion-" + name, value, unit))
        if assessment.neuropathy is not None:
            components.append(
                {
                    "code": _concept("professional-protective-sensation"),
                    "valueString": assessment.neuropathy.protective_sensation,
                }
            )
        structured = {
            "exudate-amount": assessment.exudate.amount,
            "exudate-appearance": assessment.exudate.appearance,
            "edges": ",".join(item.value for item in assessment.edges),
            "perilesional-skin": ",".join(item.value for item in assessment.perilesional_skin),
            "infection-signs-observed": ",".join(item.value for item in assessment.infection_signs)
            or "nenhum_sinal_registrado",
        }
        for name, value in structured.items():
            components.append({"code": _concept(name), "valueString": value})
        if assessment.classifications is not None:
            for name in ("ceap", "wifi", "fontaine", "lpp"):
                classification = getattr(assessment.classifications, name)
                if classification is not None:
                    values = classification.model_dump(mode="json", exclude={"review"})
                    components.append(
                        {
                            "code": _concept("professional-" + name),
                            "valueString": json.dumps(values, ensure_ascii=False),
                        }
                    )
        if analysis is not None:
            for result in analysis.get("rois", []):
                roi_id = identity("Observation", result["roi_id"]) if research else str(result["roi_id"])
                percentages = result["tissue_percentages"]
                if (
                    set(percentages) != set(TISSUE_CLASSES)
                    or any(
                        not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 100
                        for value in percentages.values()
                    )
                    or abs(sum(percentages.values()) - 100) > 0.02
                ):
                    raise ValueError("Composição assistiva inválida.")
                if (
                    result["percentages_scope"] not in {"bed", "unlocalized_roi"}
                    or not math.isfinite(result["tia_percent"])
                    or not 0 <= result["tia_percent"] <= 100
                ):
                    raise ValueError("Denominador ou taxa de incerteza inválidos.")
                for tissue, value in percentages.items():
                    components.append(_quantity(f"assistive-{roi_id}-{tissue}", value, "%"))
                components.append(_quantity(f"assistive-{roi_id}-tia-roi", result["tia_percent"], "%"))
                components.append(
                    {"code": _concept(f"assistive-{roi_id}-denominator"), "valueString": result["percentages_scope"]}
                )
            for key in ("model_version", "manifest_sha256", "status"):
                if key in analysis:
                    components.append({"code": _concept(key), "valueString": str(analysis[key])})
        if manifest_sha256:
            components.append({"code": _concept("manifest-sha256"), "valueString": manifest_sha256})
        observation = add(
            "Observation",
            assessment.assessment_id,
            status="preliminary",
            code=_concept("assistive-wound-triad", "Registro assistivo da tríade e composição tecidual"),
            subject=patient_ref,
            focus=[wound_ref],
            effectiveDateTime=date,
            performer=[practitioner_ref],
            derivedFrom=media_refs,
            method={"text": "Registro profissional e análise experimental; sem diagnóstico ou estadiamento autônomo"},
            component=components,
            note=[{"text": ASSISTIVE_DISCLAIMER}],
        )
        report = add(
            "DiagnosticReport",
            assessment.assessment_id,
            status="preliminary",
            code=_concept("assistive-follow-up", "Acompanhamento assistivo de ferida"),
            subject=patient_ref,
            effectiveDateTime=date,
            issued=assessment.review.reviewed_at.isoformat(),
            performer=[practitioner_ref],
            result=[observation_ref],
            media=[{"link": ref} for ref in media_refs],
            conclusion=ASSISTIVE_DISCLAIMER,
        )
        if assessment_revision is not None:
            report["extension"] = [
                {"url": EXTENSIONS + "source-assessment-revision", "valueInteger": assessment_revision}
            ]
        if research:
            observation.pop("effectiveDateTime", None)
            report.pop("effectiveDateTime", None)
            report.pop("issued", None)
        else:
            observation["note"].append({"text": assessment.professional_observations})
            text_report = assessment.clinical_report + "\n\n" + ASSISTIVE_DISCLAIMER
            report["presentedForm"] = [
                {
                    "contentType": "text/plain",
                    "data": base64.b64encode(text_report.encode("utf-8")).decode("ascii"),
                    "title": "Relatório assistivo revisto por profissional",
                }
            ]
        care_plan = assessment.care_plan
        if care_plan.applicable:
            plan = add(
                "CarePlan",
                assessment.assessment_id,
                status="active",
                intent="plan",
                subject=patient_ref,
                author=practitioner_ref,
                addresses=[wound_ref],
                title="Conduta registrada e revista por profissional responsável",
            )
            if not research:
                plan["description"] = care_plan.continuity_guidance
                details: list[str] = list(care_plan.procedures)
                details += [text for text in (care_plan.dressing, care_plan.therapy) if text]
                details += list(care_plan.supplies)
                if details:
                    plan["activity"] = [{"detail": {"status": "unknown", "description": text}} for text in details]
                for index, procedure in enumerate(care_plan.procedures):
                    add(
                        "Procedure",
                        f"{assessment.assessment_id}:{index}",
                        status="completed",
                        subject=patient_ref,
                        code={"text": procedure},
                        performedDateTime=date,
                        performer=[{"actor": practitioner_ref}],
                        basedOn=[reference("CarePlan", assessment.assessment_id)],
                    )
        device = getattr(assessment, "device_association", None)
        if device is not None:
            source = assessment.assessment_id
            kind = getattr(device, "device_type", "Dispositivo associado informado por profissional")
            add("Device", source, status="active", type={"text": kind if not research else "Dispositivo associado"})
            device_use = add(
                "DeviceUseStatement",
                source,
                status="active",
                subject=patient_ref,
                device=reference("Device", source),
                recordedOn=exported_at if research else date,
                reasonReference=[wound_ref],
            )
            device_use["extension"] = [
                {"url": EXTENSIONS + "device-mucosal-contact", "valueBoolean": device.mucosal_contact}
            ]
            if device.use_duration_hours is not None:
                device_use["extension"].append(
                    {
                        "url": EXTENSIONS + "device-use-duration",
                        "valueQuantity": {
                            "value": device.use_duration_hours,
                            "unit": "h",
                            "system": "http://unitsofmeasure.org",
                            "code": "h",
                        },
                    }
                )
            if not research:
                device_use["bodySite"] = {"text": device.contact_region}
        add(
            "Provenance",
            assessment.assessment_id,
            recorded=exported_at if research else assessment.review.reviewed_at.isoformat(),
            target=[{"reference": "urn:uuid:" + resource["id"]} for resource in (condition, observation, report)],
            agent=[{"who": practitioner_ref}],
            activity=_concept("human-reviewed-assistive-record"),
        )
        bundle: dict[str, Any] = {
            "resourceType": "Bundle",
            "id": str(uuid4()),
            "type": bundle_type,
            "timestamp": exported_at,
            "entry": [],
        }
        for resource in resources:
            entry = {"fullUrl": "urn:uuid:" + resource["id"], "resource": resource}
            if bundle_type == "transaction":
                entry["request"] = {"method": "PUT", "url": resource["resourceType"] + "/" + resource["id"]}
            bundle["entry"].append(entry)
        validate_bundle(bundle)
        return deepcopy(bundle)
