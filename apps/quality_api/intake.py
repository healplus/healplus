"""FHIR image intake routes; authorization runs before any request body is consumed."""

from __future__ import annotations

import hashlib
import json
import re
import threading
from typing import Callable

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPBearer
from starlette.concurrency import run_in_threadpool

from backend.supabase_client import SupabaseAuth, SupabaseClient, is_supabase_ready
from packages.shared.security import CLINICAL_WRITE_ROLES, auth_disabled, user_roles, user_uid
from src.analysis_intake.fhir import task_resource
from src.analysis_intake.repository import IntakeRepository
from src.analysis_intake.service import IntakeService
from src.image_quality.decoder import ImageInputError

MAX_BATCH_BYTES = 28 * 1024 * 1024
router = APIRouter(
    prefix="/api/v1/analyses", tags=["FHIR image intake"], dependencies=[Depends(HTTPBearer(auto_error=False))]
)


def outcome(status: int, message: str) -> JSONResponse:
    codes = {
        401: "login",
        403: "forbidden",
        404: "not-found",
        409: "conflict",
        413: "too-costly",
        415: "not-supported",
        429: "throttled",
        503: "transient",
    }
    headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    if status == 401:
        headers["WWW-Authenticate"] = "Bearer"
    if status in {429, 503}:
        headers["Retry-After"] = "5"
    return JSONResponse(
        {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "error", "code": codes.get(status, "invalid"), "details": {"text": message}}],
        },
        status_code=status,
        media_type="application/fhir+json",
        headers=headers,
    )


def authorize(request: Request) -> dict:
    if auth_disabled():
        raise ImageInputError("A recepção exige autenticação habilitada.", 503)
    verifier = request.app.state.intake_auth_verifier
    if verifier is None:
        if not is_supabase_ready():
            raise ImageInputError("Configure a autenticação antes de receber imagens.", 503)
        verifier = SupabaseAuth().verify_id_token
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer ") or not header[7:].strip():
        raise ImageInputError("Autentique-se para acessar as análises.", 401)
    token = header[7:].strip()
    try:
        user = verifier(token)
    except Exception:
        raise ImageInputError("Sessão inválida ou indisponível; autentique-se novamente.", 401) from None
    if not isinstance(user, dict) or not user_uid(user):
        raise ImageInputError("Sessão inválida.", 401)
    if not user_roles(user) & CLINICAL_WRITE_ROLES:
        raise ImageInputError("Seu perfil não permite processar imagens clínicas.", 403)
    request.state.intake_token = token
    return user


def resolve_patient(request: Request, user: dict, patient_id: str) -> dict:
    resolver = request.app.state.intake_patient_resolver
    if resolver:
        patient = resolver(user, patient_id)
    else:
        # Explicit owner predicate supplements RLS; authorization never uses client Patient data.
        rows = SupabaseClient(request.state.intake_token).select(
            "patients",
            select="id,name,birth_date",
            id=f"eq.{patient_id}",
            user_id=f"eq.{user_uid(user)}",
            archived="eq.false",
            limit="1",
        )
        patient = rows[0] if rows else None
    if not patient:
        raise ImageInputError("Paciente indisponível para este usuário.", 404)
    resource = {"resourceType": "Patient", "id": patient["id"]}
    if patient.get("name"):
        resource["name"] = [{"text": patient["name"]}]
    if patient.get("birth_date"):
        resource["birthDate"] = patient["birth_date"]
    return resource


def repository(request: Request) -> IntakeRepository:
    with request.app.state.intake_repository_lock:
        if request.app.state.intake_repository is None:
            request.app.state.intake_repository = IntakeRepository()
        return request.app.state.intake_repository


def get_record(request: Request, user: dict, analysis_id: str) -> dict:
    record = repository(request).get(analysis_id, str(user_uid(user)))
    if not record:
        raise ImageInputError("Análise não encontrada.", 404)
    # Recheck patient access on every read, including after a patient's access is revoked.
    resolve_patient(request, user, record["patient_ref"].split("/", 1)[1])
    return record


def representation(record: dict) -> dict:
    url = f"/api/v1/analyses/{record['id']}"
    return {
        "analysisId": record["id"],
        "status": record["status"],
        "statusUrl": url,
        "resultUrl": url + "/result",
        "payloadUrl": url + "/payload",
        "task": task_resource(record),
        "quality": json.loads(record["quality_json"]),
        "errorCode": record["error_code"],
    }


def unique_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def reject_constant(value: str):
    raise ValueError("invalid number")


@router.post(
    "",
    status_code=202,
    summary="Validate, store and enqueue a FHIR image batch",
    openapi_extra={
        "parameters": [
            {
                "in": "header",
                "name": "X-Patient-Consent",
                "required": True,
                "schema": {"type": "string", "enum": ["true"]},
            },
            {"in": "header", "name": "Idempotency-Key", "schema": {"type": "string", "minLength": 8, "maxLength": 128}},
        ],
        "requestBody": {
            "required": True,
            "content": {
                "application/fhir+json": {
                    "schema": {
                        "type": "object",
                        "required": ["resourceType"],
                        "properties": {"resourceType": {"type": "string", "enum": ["Media", "Bundle", "Task"]}},
                    }
                }
            },
        },
    },
)
async def submit(request: Request, user: dict = Depends(authorize)):
    if request.query_params:
        raise ImageInputError("Envie contexto clínico apenas no corpo FHIR.", 400)
    if request.headers.get("X-Patient-Consent") != "true":
        raise ImageInputError("Confirme o consentimento com X-Patient-Consent: true.", 403)
    content_type = request.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/fhir+json" or request.headers.get("Content-Encoding", "identity") != "identity":
        raise ImageInputError("Envie application/fhir+json sem compressão HTTP.", 415)
    if "fhirversion=" in request.headers.get("Content-Type", "").lower():
        version = (
            request.headers["Content-Type"].lower().split("fhirversion=", 1)[1].split(";", 1)[0].strip().strip('"')
        )
        if version not in {"4.0", "4.0.1"}:
            raise ImageInputError("Use FHIR R4 4.0.1.", 415)
    key = request.headers.get("Idempotency-Key")
    if key is not None and not re.fullmatch(r"[A-Za-z0-9._-]{8,128}", key):
        raise ImageInputError("Use Idempotency-Key com 8 a 128 caracteres opacos.", 400)
    slots = request.app.state.intake_slots
    if not slots.acquire(blocking=False):
        raise ImageInputError("Recepção ocupada; tente novamente em instantes.", 429)
    try:
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > MAX_BATCH_BYTES:
                raise ImageInputError("O lote deve ter no máximo 28 MiB.", 413)
        try:
            payload = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
        except (ValueError, UnicodeError, RecursionError):
            raise ImageInputError("JSON inválido ou com propriedades duplicadas.", 400) from None
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest()

        def accept():
            return IntakeService(repository(request)).submit(
                payload,
                owner_id=str(user_uid(user)),
                key=key,
                request_hash=digest,
                resolve_patient=lambda pid: resolve_patient(request, user, pid),
            )

        record = await run_in_threadpool(accept)
        return JSONResponse(
            representation(record),
            status_code=422 if record["status"] == "REJECTED" else 202,
            headers={"Cache-Control": "no-store", "Location": f"/api/v1/analyses/{record['id']}"},
        )
    finally:
        slots.release()


@router.get("/{analysis_id}")
def status(request: Request, analysis_id: str, user: dict = Depends(authorize)):
    record = get_record(request, user, analysis_id)
    return JSONResponse(
        {**representation(record), "history": repository(request).events(analysis_id)},
        headers={"Cache-Control": "no-store"},
    )


@router.get("/{analysis_id}/result")
def result(request: Request, analysis_id: str, user: dict = Depends(authorize)):
    record = get_record(request, user, analysis_id)
    if record["status"] in {"FAILED", "REJECTED"}:
        raise ImageInputError("Análise sem resultado; consulte o status e envie uma nova solicitação.", 409)
    if record["status"] != "COMPLETED":
        return JSONResponse(
            representation(record), status_code=202, headers={"Cache-Control": "no-store", "Retry-After": "5"}
        )
    return JSONResponse(json.loads(record["result_json"]), headers={"Cache-Control": "no-store"})


@router.get("/{analysis_id}/payload")
def payload(request: Request, analysis_id: str, user: dict = Depends(authorize)):
    record = get_record(request, user, analysis_id)
    return JSONResponse(
        json.loads(record["bundle_json"]), media_type="application/fhir+json", headers={"Cache-Control": "no-store"}
    )


@router.get("/{analysis_id}/images/{media_id}")
def image(request: Request, analysis_id: str, media_id: str, user: dict = Depends(authorize)):
    get_record(request, user, analysis_id)
    images = repository(request).images(analysis_id)
    stored = next((item for item in images if item["media_id"] == media_id), None)
    if stored is None:
        raise ImageInputError("Imagem não encontrada.", 404)
    return Response(
        stored["content"],
        media_type=stored["content_type"],
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "attachment; filename=clinical-image.jpg",
        },
    )


def initialize_intake(
    app,
    *,
    intake_repository: IntakeRepository | None = None,
    auth_verifier: Callable | None = None,
    patient_resolver: Callable | None = None,
):
    app.state.intake_repository = intake_repository
    app.state.intake_repository_lock = threading.Lock()
    app.state.intake_auth_verifier = auth_verifier
    app.state.intake_patient_resolver = patient_resolver
    app.state.intake_slots = threading.BoundedSemaphore(2)
    app.include_router(router)

    @app.middleware("http")
    async def intake_boundary(request: Request, call_next):
        if request.url.path == "/api/v1/analyses" or request.url.path.startswith("/api/v1/analyses/"):
            try:
                response = await call_next(request)
            except Exception:
                return outcome(503, "Recepção indisponível; tente novamente com a mesma Idempotency-Key.")
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response
        return await call_next(request)
