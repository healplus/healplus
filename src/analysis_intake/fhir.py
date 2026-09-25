"""Offline FHIR R4 structural validation and the bounded Heal+ intake profile."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any, Callable
import uuid

from jsonschema import Draft6Validator

from src.image_quality.decoder import ImageInputError

MAX_IMAGES = 8
ID = re.compile(r"[A-Za-z0-9\-.]{1,64}\Z")


@lru_cache
def validator(resource_type: str) -> Draft6Validator:
    schema = json.loads(Path(__file__).with_name("fhir-r4.schema.json").read_text(encoding="utf-8"))
    return Draft6Validator({**schema, "$ref": f"#/definitions/{resource_type}"})


def validate_resource(resource: dict) -> None:
    kind = resource.get("resourceType")
    if not isinstance(kind, str) or kind not in {"Media", "Bundle", "Patient", "Encounter", "Task"}:
        raise ImageInputError("Tipo de recurso FHIR não suportado.", 422)
    # Never return validator exception text: it contains the original clinical input.
    if next(validator(kind).iter_errors(resource), None) is not None:
        raise ImageInputError("Recurso inválido para a estrutura FHIR R4 4.0.1.", 422)


def prepare_bundle(payload: object, resolve_patient: Callable[[str], dict]) -> dict[str, Any]:
    """Complete patient context only from an authorized, authoritative lookup."""
    if not isinstance(payload, dict):
        raise ImageInputError("Envie Media, Bundle collection ou Task com recursos contidos.", 422)
    validate_resource(payload)
    payload = deepcopy(payload)
    if payload.get("modifierExtension"):
        raise ImageInputError("Modificadores não suportados pelo perfil de recepção.", 422)
    kind = payload["resourceType"]
    task = None
    entries: list[dict[str, Any]]
    if kind == "Media":
        entries = [{"resource": payload}]
    elif kind == "Bundle" and payload.get("type") == "collection":
        entries = payload.get("entry", [])
    elif kind == "Task":
        task = payload
        entries = [{"fullUrl": f"#{r.get('id', '')}", "resource": r} for r in task.get("contained", [])]
    else:
        raise ImageInputError("Use Bundle do tipo collection.", 422)
    if not 1 <= len(entries) <= MAX_IMAGES + 3:
        raise ImageInputError("Lote vazio ou acima do limite de recursos.", 422)

    resources, aliases, identities = [], {}, set()
    for entry in entries:
        resource = entry.get("resource")
        if not isinstance(resource, dict):
            raise ImageInputError("Cada entrada deve conter um recurso FHIR.", 422)
        resource_type = resource.get("resourceType")
        if (
            resource_type not in {"Media", "Patient", "Encounter", "Task"}
            or resource.get("contained")
            or resource.get("modifierExtension")
        ):
            raise ImageInputError("Recurso ou modificador fora do perfil de recepção.", 422)
        resource.setdefault("id", str(uuid.uuid4()))
        if not isinstance(resource["id"], str) or not ID.fullmatch(resource["id"]):
            raise ImageInputError("Identificador FHIR inválido.", 422)
        identity = f"{resource_type}/{resource['id']}"
        if identity in identities:
            raise ImageInputError("Recursos duplicados no lote.", 422)
        identities.add(identity)
        alias = entry.get("fullUrl", identity)
        if alias in aliases or identity in aliases:
            raise ImageInputError("Referências duplicadas no lote.", 422)
        aliases[alias] = identity
        aliases[identity] = identity
        resources.append(resource)

    def reference(value: Any, expected: str) -> str:
        raw = value.get("reference") if isinstance(value, dict) else None
        canonical = aliases.get(raw, raw) if isinstance(raw, str) else None
        if (
            not isinstance(canonical, str)
            or not canonical.startswith(expected + "/")
            or not ID.fullmatch(canonical[len(expected) + 1 :])
        ):
            raise ImageInputError("Use referências locais válidas para paciente e atendimento.", 422)
        return canonical

    tasks = [r for r in resources if r["resourceType"] == "Task"] + ([task] if task else [])
    patients = [r for r in resources if r["resourceType"] == "Patient"]
    encounters = [r for r in resources if r["resourceType"] == "Encounter"]
    media = [r for r in resources if r["resourceType"] == "Media"]
    if not 1 <= len(media) <= MAX_IMAGES or len(patients) > 1 or len(encounters) > 1 or len(tasks) > 1:
        raise ImageInputError("Envie de 1 a 8 imagens de um único paciente e atendimento.", 422)
    if tasks:
        incoming_task = tasks[0]
        if incoming_task.get("status") != "requested" or incoming_task.get("intent") != "order":
            raise ImageInputError("Envie uma Task requested com intent order.", 422)
        media_refs = {f"Media/{r['id']}" for r in media}
        for task_input in incoming_task.get("input", []):
            if reference(task_input.get("valueReference"), "Media") not in media_refs:
                raise ImageInputError("Task.input deve referenciar uma imagem do lote.", 422)
    default_patient = {"reference": f"Patient/{patients[0]['id']}"} if patients else None
    if tasks and tasks[0].get("for"):
        task_patient = reference(tasks[0]["for"], "Patient")
        if default_patient and task_patient != default_patient["reference"]:
            raise ImageInputError("Paciente da tarefa diverge do lote.", 422)
        default_patient = {"reference": task_patient}
    default_encounter = {"reference": f"Encounter/{encounters[0]['id']}"} if encounters else None
    if tasks and tasks[0].get("encounter"):
        task_encounter = reference(tasks[0]["encounter"], "Encounter")
        if default_encounter and task_encounter != default_encounter["reference"]:
            raise ImageInputError("Atendimento da tarefa diverge do lote.", 422)
        default_encounter = {"reference": task_encounter}
    subjects, visits = set(), set()
    for item in media:
        item["subject"] = {"reference": reference(item.get("subject", default_patient), "Patient")}
        subjects.add(item["subject"]["reference"])
        if item.get("encounter") or default_encounter:
            item["encounter"] = {"reference": reference(item.get("encounter", default_encounter), "Encounter")}
            visits.add(item["encounter"]["reference"])
        if item.get("status") != "completed" or not item.get("createdDateTime"):
            raise ImageInputError("Media exige status completed e createdDateTime da captura.", 422)
        try:
            captured = datetime.fromisoformat(item["createdDateTime"])
            if "T" not in item["createdDateTime"] or captured.tzinfo is None:
                raise ValueError("missing timestamp timezone")
        except ValueError:
            raise ImageInputError("Informe a data/hora real da captura com fuso horário.", 422) from None
        content = item.get("content", {})
        if content.get("contentType") != "image/jpeg" or not content.get("data") or content.get("url"):
            raise ImageInputError("Envie JPEG inline em Media.content.data, sem URL.", 415)
        if item.get("type", {}).get("coding") and not any(
            c.get("code") == "image" and c.get("system") == "http://terminology.hl7.org/CodeSystem/media-type"
            for c in item["type"]["coding"]
        ):
            raise ImageInputError("Media.type deve identificar uma imagem.", 422)
    if len(subjects) != 1 or len(visits) > 1:
        raise ImageInputError("Não misture pacientes ou atendimentos no lote.", 422)
    patient_ref = next(iter(subjects))
    if default_patient and patient_ref != default_patient["reference"]:
        raise ImageInputError("Paciente informado diverge das imagens.", 422)
    if default_encounter and visits != {default_encounter["reference"]}:
        raise ImageInputError("Atendimento informado diverge das imagens.", 422)
    for encounter in encounters:
        if reference(encounter.get("subject"), "Patient") != patient_ref:
            raise ImageInputError("Atendimento pertence a outro paciente.", 422)
        encounter["subject"] = {"reference": patient_ref}
    patient = resolve_patient(patient_ref.split("/", 1)[1])
    if patient.get("resourceType") != "Patient" or f"Patient/{patient.get('id')}" != patient_ref:
        raise ImageInputError("Paciente indisponível para este usuário.", 404)
    completed = {
        "resourceType": "Bundle",
        "id": str(uuid.uuid4()),
        "type": "collection",
        "entry": [{"resource": r} for r in [patient, *encounters, *media]],
    }
    validate_resource(completed)
    return completed


def task_resource(record: dict) -> dict:
    status = {
        "ACCEPTED": "accepted",
        "QUEUED": "ready",
        "PROCESSING": "in-progress",
        "COMPLETED": "completed",
        "FAILED": "failed",
        "REJECTED": "rejected",
    }[record["status"]]
    task = {
        "resourceType": "Task",
        "id": record["id"],
        "status": status,
        "intent": "order",
        "code": {"text": "Heal+ wound image analysis"},
        "for": {"reference": record["patient_ref"]},
        "authoredOn": record["created_at"],
        "lastModified": record["updated_at"],
        "businessStatus": {"text": record["status"]},
        "focus": {"reference": f"Bundle/{record['bundle_id']}"},
    }
    if record.get("encounter_ref"):
        task["encounter"] = {"reference": record["encounter_ref"]}
    if record["status"] == "COMPLETED":
        task["output"] = [
            {"type": {"text": "Heal+ analysis result"}, "valueUrl": f"/api/v1/analyses/{record['id']}/result"}
        ]
    return task
