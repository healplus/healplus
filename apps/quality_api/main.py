# -*- coding: utf-8 -*-
"""Official FastAPI application for clinical image quality assessment and FHIR R4 interoperability."""

from __future__ import annotations

import base64
import os
import uuid
from typing import Any, Dict, List, Optional

import cv2
from fastapi import Body, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.image_quality.decoder import ImageInputError
from src.image_quality.fhir import capability_statement, operation_definition, parse_parameters, result_parameters
from src.image_quality.service import ImageQualityService, QualityAssessmentResult


class QualityAssessmentRequestJSON(BaseModel):
    image_base64: str = Field(..., description="Base64-encoded JPEG or PNG image bytes")
    content_type: str = Field(default="image/jpeg", description="MIME type (image/jpeg or image/png)")
    filename: Optional[str] = Field(default="wound.jpg", description="Original filename")
    patient_id: Optional[str] = Field(default=None, description="Patient technical identifier")
    encounter_id: Optional[str] = Field(default=None, description="Encounter or consultation identifier")
    image_id: Optional[str] = Field(default=None, description="Image opaque correlation identifier")
    consent: bool = Field(default=True, description="Confirmation of clinical action and patient consent")


def create_fastapi_app(service: Optional[ImageQualityService] = None) -> FastAPI:
    quality_service = service or ImageQualityService()

    app = FastAPI(
        title="Heal+ Clinical Image Quality & FHIR R4 API",
        version="1.0.0",
        description=(
            "Serviço FastAPI de triagem técnica de fotografias clínicas de feridas. "
            "Avalia nitidez, iluminação, resolução e contraste via OpenCV + Pillow, "
            "preserva o arquivo original em armazenamento privado com auditoria de transformações "
            "e gera recursos Media e Observation compatíveis com FHIR R4."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Configure CORS
    allowed_origin = os.getenv("CLINICAL_API_ALLOWED_ORIGIN", "*")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[allowed_origin] if allowed_origin != "*" else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ImageInputError)
    async def image_input_error_handler(request: Request, exc: ImageInputError):
        accept = request.headers.get("Accept", "")
        if "application/fhir+json" in accept:
            return JSONResponse(
                status_code=exc.status,
                content={
                    "resourceType": "OperationOutcome",
                    "issue": [
                        {
                            "severity": "error",
                            "code": "invalid" if exc.status == 400 else "not-supported" if exc.status == 415 else "too-costly" if exc.status == 413 else "forbidden" if exc.status == 403 else "structure",
                            "details": {"text": str(exc)},
                        }
                    ],
                },
                media_type="application/fhir+json; charset=utf-8",
                headers={"Cache-Control": "no-store"},
            )
        return JSONResponse(
            status_code=exc.status,
            content={"error": "image_input_error", "message": str(exc), "status_code": exc.status},
        )

    @app.get("/api/v1/quality/health", tags=["Monitoring"])
    async def health_check():
        return {
            "status": "ok",
            "service": "healplus-image-quality-fastapi",
            "version": "1.0.0",
            "engine": {
                "opencv": cv2.__version__,
                "algorithm": "healplus-iqa-1.0.0",
            },
            "capabilities": {
                "opencv_sharpness": True,
                "opencv_lighting": True,
                "opencv_resolution": True,
                "fhir_r4_media": True,
                "fhir_r4_observation": True,
                "private_storage": True,
            },
        }

    @app.post("/api/v1/quality/assess", tags=["Quality Assessment"])
    async def assess_image_endpoint(
        request: Request,
        file: Optional[UploadFile] = File(None),
        patient_id: Optional[str] = Form(None),
        encounter_id: Optional[str] = Form(None),
        image_id: Optional[str] = Form(None),
        consent: bool = Form(True),
    ):
        """Avalia qualidade técnica de imagem clínica via multipart/form-data ou JSON."""
        content_type_header = request.headers.get("Content-Type", "")

        if "application/json" in content_type_header:
            body_data = await request.json()
            raw_base64 = body_data.get("image_base64", "")
            if not raw_base64:
                raise ImageInputError("Campo 'image_base64' é obrigatório no corpo JSON.", 400)
            try:
                raw_bytes = base64.b64decode(raw_base64, validate=True)
            except Exception:
                raise ImageInputError("Conteúdo 'image_base64' inválido.", 400)
            filename = body_data.get("filename", "wound.jpg")
            content_type = body_data.get("content_type", "image/jpeg")
            patient_id = body_data.get("patient_id")
            encounter_id = body_data.get("encounter_id")
            image_id = body_data.get("image_id")
            consent = body_data.get("consent", True)
        elif file is not None:
            raw_bytes = await file.read()
            filename = file.filename or "wound.jpg"
            content_type = file.content_type or "image/jpeg"
        else:
            raise ImageInputError("Envie um arquivo multipart ('file') ou payload JSON ('image_base64').", 400)

        result: QualityAssessmentResult = quality_service.assess_image_bytes(
            raw_bytes,
            filename=filename,
            content_type=content_type,
            patient_id=patient_id,
            encounter_id=encounter_id,
            image_id=image_id,
            consent=consent,
        )
        return result.to_dict()

    @app.post("/api/v1/quality/fhir/$validate-image", tags=["FHIR R4 Operations"])
    async def fhir_validate_image(request: Request):
        """Operação FHIR R4 $validate-image, aceitando recurso Parameters."""
        payload = await request.json()
        image_id, attachment_dict = parse_parameters(payload)

        raw_b64 = attachment_dict.get("data", "")
        mime = attachment_dict.get("contentType", "image/jpeg")
        try:
            raw_bytes = base64.b64decode(raw_b64, validate=True)
        except Exception:
            raise ImageInputError("Base64 de imagem inválido.", 400)

        result: QualityAssessmentResult = quality_service.assess_image_bytes(
            raw_bytes,
            filename=f"{image_id}.jpg" if mime == "image/jpeg" else f"{image_id}.png",
            content_type=mime,
            image_id=image_id,
            consent=True,
        )

        request_id = str(uuid.uuid4())
        # Format response parameters
        from src.image_quality.assessment import Assessment, Finding
        findings_tuple = tuple(
            Finding(f["code"], f["severity"], f["message"])
            for f in result.findings
        )
        compat_assessment = Assessment(
            status=result.status,
            metrics=result.metrics,
            findings=findings_tuple,
        )
        fhir_resp = result_parameters(compat_assessment, image_id, request_id)
        return JSONResponse(
            content=fhir_resp,
            media_type="application/fhir+json; charset=utf-8",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/v1/quality/fhir/metadata", tags=["FHIR R4 Operations"])
    async def fhir_metadata():
        """Retorna CapabilityStatement FHIR 4.0.1 do serviço de qualidade."""
        return JSONResponse(
            content=capability_statement(),
            media_type="application/fhir+json; charset=utf-8",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/v1/quality/fhir/OperationDefinition/validate-image", tags=["FHIR R4 Operations"])
    async def fhir_operation_definition():
        return JSONResponse(
            content=operation_definition(),
            media_type="application/fhir+json; charset=utf-8",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/v1/quality/evaluations/{evaluation_id}", tags=["Evaluation History"])
    async def get_evaluation_by_id(evaluation_id: str):
        record = quality_service.get_evaluation(evaluation_id)
        if not record:
            raise HTTPException(status_code=404, detail="Avaliação não encontrada.")
        return record.to_dict()

    @app.get("/api/v1/quality/patients/{patient_id}/evaluations", tags=["Evaluation History"])
    async def get_evaluations_by_patient(patient_id: str):
        records = quality_service.list_patient_evaluations(patient_id)
        return [r.to_dict() for r in records]

    return app


# Default ASGI app instance for uvicorn
app = create_fastapi_app()
