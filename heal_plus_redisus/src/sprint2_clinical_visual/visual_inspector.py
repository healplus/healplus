"""Professional annotation protocol; no image-to-diagnosis or automatic staging.

Feature values describe a *reviewed factor*, not a diagnosis. Missing observations
remain unknown. In particular, a dark pixel never establishes necrosis or skin tone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..safety import ASSISTIVE_DISCLAIMER


class ObservationState(str, Enum):
    PRESENT = "presente"
    ABSENT = "ausente"
    UNKNOWN = "desconhecido"
    NOT_ASSESSED = "nao_avaliado"


class SkinTone(str, Enum):
    LIGHT = "claro"
    INTERMEDIATE = "intermediario"
    DARK = "escuro_retinto"
    UNKNOWN = "desconhecido"


@dataclass(frozen=True)
class FeatureDefinition:
    code: str
    dimension: str
    label: str
    professional_review_required: bool = True


FEATURES = (
    FeatureDefinition("F01", "fotografia", "Distância fora do protocolo 20–30 cm"),
    FeatureDefinition("F02", "fotografia", "Ângulo frontal fora do protocolo de 90°"),
    FeatureDefinition("F03", "fotografia", "Sombra, reflexo ou iluminação inconsistente"),
    FeatureDefinition("F04", "fotografia", "Desfoque ou perda de nitidez"),
    FeatureDefinition("F05", "fotografia", "Fundo não neutro ou distrator"),
    FeatureDefinition("F06", "fotografia", "Escala ausente, inadequada ou sobreposta"),
    FeatureDefinition("F07", "fotografia", "Identificadores ou exposição desnecessária"),
    FeatureDefinition("C01", "triade", "Possível confusão entre adiposo e esfacelo/fibrina"),
    FeatureDefinition("C02", "triade", "Leito encoberto; profundidade não observável"),
    FeatureDefinition("C03", "triade", "Hiperqueratose ou alteração de borda"),
    FeatureDefinition("C04", "triade", "Exsudato, umidade ou maceração"),
    FeatureDefinition("C05", "triade", "Hipergranulação, sangue ou coágulo"),
    FeatureDefinition("C06", "triade", "Alteração de pele perilesional"),
    FeatureDefinition("C07", "triade", "Mudança associada a desbridamento"),
    FeatureDefinition("C08", "triade", "Dispositivo médico associado"),
    FeatureDefinition("E01", "equidade", "Tom de pele escuro/retinto anotado no protocolo de equidade"),
    FeatureDefinition("E02", "equidade", "Alteração sutil em pele escura exige revisão"),
    FeatureDefinition("E03", "contexto", "Etiologia documentada pelo profissional"),
    FeatureDefinition("X01", "triade", "Curativo ou material cobrindo o leito"),
    FeatureDefinition("X02", "triade", "Borda fora de quadro ou ocluída"),
    FeatureDefinition("X03", "triade", "Margem de pele perilesional insuficiente"),
    FeatureDefinition("X04", "contexto", "Perfusão/isquemia avaliada presencialmente"),
    FeatureDefinition("X05", "contexto", "Dor e sensibilidade registradas pelo profissional"),
    FeatureDefinition("X06", "fotografia", "Protocolo comparável ao registro anterior"),
)
FEATURE_CATALOG = {feature.code: feature for feature in FEATURES}


class EquityCounts(BaseModel):
    """Expert-labelled denominators; never estimated from the image colour."""

    model_config = ConfigDict(extra="forbid")
    necrosis_false_positive_pixels: int | None = Field(default=None, ge=0)
    non_necrosis_reference_pixels: int | None = Field(default=None, ge=0)
    erythema_false_negative_pixels: int | None = Field(default=None, ge=0)
    erythema_reference_pixels: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> "EquityCounts":
        for numerator, denominator in (
            (self.necrosis_false_positive_pixels, self.non_necrosis_reference_pixels),
            (self.erythema_false_negative_pixels, self.erythema_reference_pixels),
        ):
            if (numerator is None) != (denominator is None):
                raise ValueError("Informe numerador e denominador de referência juntos.")
            if numerator is not None and denominator is not None and numerator > denominator:
                raise ValueError("O numerador não pode exceder a referência.")
        return self


class VisualInspection(BaseModel):
    """Pseudonymous annotation row. Scores and TIA are fractions in [0, 1].

    ``reviewer_id`` identifies a professional inside the protected application;
    names, patient records and clinical free text are intentionally unnecessary.
    Skin tone is supplied by the approved annotation protocol, never inferred.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    image_id: str = Field(min_length=1, max_length=160)
    dataset_id: str = Field(min_length=1, max_length=160)
    category: Literal["A", "B", "C", "D", "E", "INTERMEDIATE"]
    skin_tone: SkinTone = SkinTone.UNKNOWN
    features: dict[str, ObservationState] = Field(default_factory=dict)
    etiology: Literal["pressao", "venosa", "arterial", "pe_diabetico", "cirurgica_outra", "desconhecida"] = (
        "desconhecida"
    )
    reviewer_id: str | None = Field(default=None, min_length=1, max_length=160)
    reviewed_at: datetime | None = None
    clinical_context_fields: set[str] = Field(default_factory=set)
    dice: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    detector_iou: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    tia: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    equity_counts: EquityCounts = Field(default_factory=EquityCounts)

    @field_validator("features")
    @classmethod
    def validate_features(cls, values: dict[str, ObservationState]) -> dict[str, ObservationState]:
        if set(values) - FEATURE_CATALOG.keys():
            raise ValueError("Código de característica não reconhecido no protocolo.")
        return values

    @model_validator(mode="after")
    def validate_review(self) -> "VisualInspection":
        if (self.reviewer_id is None) != (self.reviewed_at is None):
            raise ValueError("Revisor e data da revisão devem ser informados juntos.")
        if self.reviewed_at is not None and self.reviewed_at.utcoffset() is None:
            raise ValueError("A data da revisão deve conter fuso horário.")
        return self

    def state(self, code: str) -> ObservationState:
        if code not in FEATURE_CATALOG:
            raise ValueError("Código de característica não reconhecido no protocolo.")
        return self.features.get(code, ObservationState.UNKNOWN)


@dataclass(frozen=True)
class InspectionReport:
    image_id: str
    feature_states: dict[str, ObservationState]
    reviewed: bool
    review_prompts: tuple[str, ...]
    required_clinical_fields: tuple[str, ...]
    missing_clinical_fields: tuple[str, ...]
    disclaimer: str = ASSISTIVE_DISCLAIMER


class ClinicalVisualInspector:
    """Return explicit review tasks from annotations, without classifying pixels."""

    def inspect(self, inspection: VisualInspection) -> InspectionReport:
        states = {code: inspection.state(code) for code in FEATURE_CATALOG}
        prompts: list[str] = []
        if inspection.reviewer_id is None:
            prompts.append("Anotação provisória: solicitar revisão por profissional habilitado.")
        if inspection.tia is not None and inspection.tia >= 0.25:
            prompts.append(
                "Incerteza assistiva elevada: solicitar revisão humana ou nova captura antes de interpretar os percentuais."
            )
        if states["C01"] == ObservationState.PRESENT:
            prompts.append(
                "Revisar adiposo e esfacelo/fibrina com textura, localização e contexto clínico; a cor isolada não diferencia tecidos."
            )
        if states["C02"] == ObservationState.PRESENT:
            prompts.append(
                "Leito encoberto: a profundidade real não pode ser estimada visualmente; solicitar avaliação presencial pelo profissional."
            )
        if states["C03"] == ObservationState.PRESENT:
            prompts.append(
                "Revisar separadamente leito, borda e pele perilesional para evitar incluir hiperqueratose no leito."
            )
        if states["C05"] == ObservationState.PRESENT:
            prompts.append(
                "Revisar sangue/coágulo, reflexos e tecido com apoio clínico; manter regiões ambíguas em baixa confiança."
            )
        if any(states[code] == ObservationState.PRESENT for code in ("E01", "E02")):
            prompts.append(
                "Revisar com referência perilesional da própria pessoa; pigmentação e alteração sutil não estabelecem necrose, eritema ou estágio por fotografia."
            )
        if states["C07"] == ObservationState.PRESENT:
            prompts.append("Registrar data e contexto do desbridamento antes de interpretar diferenças entre imagens.")
        if states["C08"] == ObservationState.PRESENT:
            prompts.append("Registrar tipo de dispositivo, região de contato/mucosa e tempo de uso.")
        required_by_etiology = {
            "pressao": ("avaliacao_presencial", "estruturas_expostas", "classificacao_lpp_profissional"),
            "venosa": ("ceap_c", "ceap_e", "ceap_a", "ceap_p"),
            "arterial": ("wifi_w", "wifi_i", "wifi_fi", "fontaine", "perfusao"),
            "pe_diabetico": ("wifi_w", "wifi_i", "wifi_fi", "perfusao", "neuropatia"),
        }
        required = required_by_etiology.get(inspection.etiology, ())
        missing = tuple(field for field in required if field not in inspection.clinical_context_fields)
        if missing:
            prompts.append(
                "Completar os campos clínicos com avaliação profissional; a análise fotográfica não atribui classificação ou estágio."
            )
        return InspectionReport(
            inspection.image_id, states, inspection.reviewer_id is not None, tuple(prompts), required, missing
        )
