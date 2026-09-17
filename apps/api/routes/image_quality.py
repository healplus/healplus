"""Stateless FHIR R4 image-quality operation with bounded CPU and input size."""

from __future__ import annotations

import json
import threading
from typing import Any, NoReturn

from flask import Blueprint, Flask, Response, abort, current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException

from packages.shared.security import (
    auth_disabled,
    current_user_required,
    enforce_rate_limit,
    enforce_request_auth,
    ensure_clinical_write_access,
    get_rate_limit_window,
)
from src.image_quality.assessment import assess_image
from src.image_quality.decoder import MAX_REQUEST_BYTES, ImageInputError, decode_attachment
from src.image_quality.fhir import (
    FHIR_PATH,
    capability_statement,
    operation_definition,
    parse_parameters,
    result_parameters,
)

image_quality_api = Blueprint("image_quality_api", __name__, url_prefix=FHIR_PATH)


def is_quality_request() -> bool:
    return request.path == FHIR_PATH or request.path.startswith(FHIR_PATH + "/")


def fhir_response(payload: dict, status: int = 200) -> Response:
    response = jsonify(payload)
    response.status_code = status
    response.content_type = "application/fhir+json; charset=utf-8"
    response.headers["Cache-Control"] = "no-store"
    if status == 429:
        response.headers["Retry-After"] = str(get_rate_limit_window())
    if status == 401:
        response.headers["WWW-Authenticate"] = "Bearer"
    return response


def fhir_error(status: int, message: str | None = None) -> Response:
    codes = {
        400: "invalid",
        401: "login",
        403: "forbidden",
        404: "not-found",
        405: "not-supported",
        406: "not-supported",
        413: "too-costly",
        415: "not-supported",
        422: "invalid",
        429: "throttled",
        503: "transient",
    }
    messages = {
        400: "Revise o recurso Parameters enviado.",
        401: "Autentique-se novamente para enviar a imagem.",
        403: "Seu perfil não está autorizado ou o consentimento não foi confirmado.",
        404: "Operação FHIR não encontrada.",
        405: "Use o método HTTP documentado para esta operação.",
        406: "Solicite uma resposta application/fhir+json.",
        413: "Reduza a imagem ou o tamanho da requisição.",
        415: "Use application/fhir+json e uma imagem JPEG ou PNG.",
        422: "Envie uma imagem válida e íntegra.",
        429: "Limite de processamento atingido; aguarde e tente novamente.",
        503: "Validação indisponível; a autenticação deve estar configurada e habilitada.",
    }
    return fhir_response(
        {
            "resourceType": "OperationOutcome",
            "issue": [
                {
                    "severity": "error",
                    "code": codes.get(status, "exception"),
                    "details": {
                        "text": message
                        or messages.get(status, "Não foi possível processar a imagem; tente novamente mais tarde.")
                    },
                }
            ],
        },
        status,
    )


def initialize_quality_api(app: Flask) -> None:
    app.extensions["image_quality_slots"] = threading.BoundedSemaphore(2)
    app.register_blueprint(image_quality_api)


def authenticate_quality_request() -> None:
    if auth_disabled():
        abort(503)
    verifier = current_app.config.get("REDISUS_AUTH_VERIFIER")
    if verifier is None:
        verifier = current_app.extensions.get("redisus_auth_verifier")
    if verifier is None:
        abort(503)
    # Injectable callables own token verification; Firebase must also check revocation.
    verify = verifier if callable(verifier) else lambda token: verifier.verify_id_token(token, check_revoked=True)
    enforce_request_auth(verify)


@image_quality_api.before_request
def quality_security() -> None:
    # The clinical app supports a development auth bypass. This new upload boundary never does.
    if request.method == "OPTIONS":
        return None
    if auth_disabled():
        abort(503)
    ensure_clinical_write_access(current_user_required())
    if request.headers.get("Accept") and request.accept_mimetypes["application/fhir+json"] <= 0:
        abort(406)
    if request.args:
        abort(400)
    return None


@image_quality_api.get("/metadata")
def metadata() -> Response:
    return fhir_response(capability_statement())


@image_quality_api.get("/OperationDefinition/validate-image")
def definition() -> Response:
    return fhir_response(operation_definition())


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate property")
        obj[key] = value
    return obj


def _reject_constant(_value: str) -> NoReturn:
    raise ValueError("non-finite JSON number")


@image_quality_api.post("/$validate-image")
def validate_image() -> Response:
    enforce_rate_limit("image_quality", default_limit=30)
    if request.mimetype != "application/fhir+json":
        abort(415)
    if request.mimetype_params.get("fhirversion", "4.0") not in {"4.0", "4.0.1"}:
        abort(415)
    if request.content_encoding and request.content_encoding.lower() != "identity":
        abort(415)
    if request.content_length is not None and request.content_length > MAX_REQUEST_BYTES:
        abort(413)
    slots = current_app.extensions["image_quality_slots"]
    if not slots.acquire(blocking=False):
        abort(429)
    try:
        raw = request.stream.read(MAX_REQUEST_BYTES + 1)
        if len(raw) > MAX_REQUEST_BYTES:
            abort(413)
        try:
            payload = json.loads(
                raw,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
        except (ValueError, UnicodeError, RecursionError):
            abort(400)
        image_id, attachment = parse_parameters(payload)
        image = decode_attachment(attachment)
        result = assess_image(image)
        return fhir_response(result_parameters(result, image_id, g.redisus_request_id))
    except ImageInputError as exc:
        return fhir_error(exc.status, str(exc))
    except HTTPException:
        raise
    except Exception:
        # No exception traceback: third-party decoder messages can contain untrusted metadata.
        return fhir_error(500)
    finally:
        slots.release()
