"""FHIR R4 operation contract and result mapping, independent of HTTP transport."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .assessment import ALGORITHM_VERSION, LIMITATION, Assessment, policy_values
from .decoder import ImageInputError

FHIR_BASE = "https://healplus.local/fhir"
CODE_SYSTEM = f"{FHIR_BASE}/CodeSystem/image-quality"
OPERATION_URL = f"{FHIR_BASE}/OperationDefinition/validate-image"
FHIR_PATH = "/api/v1/fhir"


def parse_parameters(payload: object) -> tuple[str, dict]:
    if (
        not isinstance(payload, dict)
        or set(payload) != {"resourceType", "parameter"}
        or payload["resourceType"] != "Parameters"
    ):
        raise ImageInputError("Envie um recurso FHIR R4 Parameters com imageId, consent e image.")
    parameters = payload["parameter"]
    if not isinstance(parameters, list) or len(parameters) != 3:
        raise ImageInputError("Informe exatamente imageId, consent e image, sem parâmetros repetidos.")
    fields = {"imageId": "valueString", "consent": "valueBoolean", "image": "valueAttachment"}
    values: dict[str, Any] = {}
    for item in parameters:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ImageInputError("Parâmetro FHIR inválido.")
        name = item["name"]
        if name not in fields or name in values or set(item) != {"name", fields[name]}:
            raise ImageInputError("Parâmetro desconhecido, repetido ou com tipo incorreto.")
        values[name] = item[fields[name]]
    image_id = values["imageId"]
    if not isinstance(image_id, str) or re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", image_id) is None:
        raise ImageInputError("imageId deve ser um identificador técnico de 8 a 128 caracteres, sem dados pessoais.")
    if values["consent"] is not True:
        raise ImageInputError("Confirme o consentimento para processar esta imagem antes de enviá-la.", 403)
    return image_id, values["image"]


def concept(code: str, text: str | None = None) -> dict:
    result: dict[str, Any] = {"coding": [{"system": CODE_SYSTEM, "code": code}]}
    if text:
        result["text"] = text
    return result


def result_parameters(result: Assessment, image_id: str, request_id: str) -> dict:
    observation = {
        "resourceType": "Observation",
        "status": "final",
        "code": concept("technical-image-quality", "Qualidade técnica de imagem"),
        "effectiveDateTime": datetime.now(timezone.utc).isoformat(),
        "valueCodeableConcept": concept(result.status),
        "method": concept(ALGORITHM_VERSION),
        "note": [{"text": LIMITATION}],
        "component": [
            {
                "code": concept(name),
                "valueQuantity": {"value": value, "unit": "pixels" if "width" in name or "height" in name else "score"},
            }
            for name, value in result.metrics.items()
        ],
    }
    parameters = [
        {"name": "contractVersion", "valueString": "1.0"},
        {"name": "requestId", "valueUuid": f"urn:uuid:{request_id}"},
        {"name": "imageId", "valueString": image_id},
        {"name": "status", "valueCode": result.status},
        {"name": "algorithmVersion", "valueString": ALGORITHM_VERSION},
        {"name": "validationStage", "valueCode": "experimental"},
        {"name": "limitation", "valueString": LIMITATION},
        {"name": "measurement", "resource": observation},
        *[
            {
                "name": "reason",
                "part": [
                    {"name": "code", "valueCode": finding.code},
                    {"name": "severity", "valueCode": finding.severity},
                    {"name": "message", "valueString": finding.message},
                ],
            }
            for finding in result.findings
        ],
        *[
            {
                "name": "threshold",
                "part": [
                    {"name": "name", "valueCode": name},
                    {"name": "value", "valueDecimal": value},
                ],
            }
            for name, value in policy_values().items()
        ],
    ]
    return {"resourceType": "Parameters", "parameter": parameters}


def operation_definition() -> dict:
    def parameter(name: str, use: str, kind: str, documentation: str, minimum: int = 1, maximum: str = "1") -> dict:
        return {"name": name, "use": use, "min": minimum, "max": maximum, "type": kind, "documentation": documentation}

    return {
        "resourceType": "OperationDefinition",
        "id": "validate-image",
        "url": OPERATION_URL,
        "version": "1.0",
        "name": "ValidateImage",
        "status": "draft",
        "kind": "operation",
        "experimental": True,
        "date": "2026-09-17",
        "publisher": "Heal+",
        "description": LIMITATION,
        "affectsState": False,
        "code": "validate-image",
        "system": True,
        "type": False,
        "instance": False,
        "parameter": [
            parameter(
                "imageId",
                "in",
                "string",
                "Identificador técnico de 8 a 128 caracteres [A-Za-z0-9._:-], sem dados pessoais.",
            ),
            parameter(
                "consent", "in", "boolean", "Deve ser true: confirmação da ação e consentimento para processamento."
            ),
            parameter(
                "image",
                "in",
                "Attachment",
                "Somente contentType (image/jpeg ou image/png) e data base64. Até 10 MiB e 12 MP; sem URL, transparência ou animação.",
            ),
            parameter("contractVersion", "out", "string", "Versão do contrato de resultado técnico: 1.0."),
            parameter("requestId", "out", "uuid", "Identificador criado pelo servidor para esta execução."),
            parameter("imageId", "out", "string", "Identificador técnico enviado."),
            parameter(
                "status", "out", "code", "accepted, rejected ou indeterminate; qualidade técnica, nunca diagnóstico."
            ),
            parameter("algorithmVersion", "out", "string", "Versão dos algoritmos e limites utilizados."),
            parameter("validationStage", "out", "code", "experimental: requer calibração externa."),
            parameter("limitation", "out", "string", "Limitações da interpretação."),
            parameter(
                "measurement", "out", "Observation", "Métricas da imagem inteira; recurso não persistido e sem id."
            ),
            {
                "name": "reason",
                "use": "out",
                "min": 0,
                "max": "*",
                "part": [
                    parameter("code", "out", "code", "Código estável do achado."),
                    parameter("severity", "out", "code", "error ou warning."),
                    parameter("message", "out", "string", "Orientação para revisar ou repetir a captura."),
                ],
            },
            {
                "name": "threshold",
                "use": "out",
                "min": 1,
                "max": "*",
                "part": [
                    parameter("name", "out", "code", "Nome do limite."),
                    parameter("value", "out", "decimal", "Valor aplicado nesta versão."),
                ],
            },
        ],
    }


def capability_statement() -> dict:
    return {
        "resourceType": "CapabilityStatement",
        "status": "draft",
        "experimental": True,
        "date": "2026-09-17",
        "kind": "capability",
        "fhirVersion": "4.0.1",
        "format": ["application/fhir+json"],
        "description": "Serviço de qualidade técnica de imagens. Não implementa CRUD de prontuários ou publicação RNDS.",
        "rest": [
            {
                "mode": "server",
                "security": {
                    "description": "Bearer token verificado pelo backend e papel clínico autorizado; TLS obrigatório no gateway."
                },
                "operation": [{"name": "validate-image", "definition": OPERATION_URL}],
            }
        ],
    }
