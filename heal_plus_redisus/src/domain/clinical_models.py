"""Validated clinical *records*, never automatic clinical decisions.

The RC identifiers refer to RT-HEAL-001. UUID references and a pseudonym replace
direct identifiers; the identity registry belongs in a separately secured service.
All categorical clinical observations and classifications must be entered/reviewed
by a qualified professional. No score or stage is inferred from image features.
"""

from __future__ import annotations

from enum import Enum
from math import isclose
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from ..safety import ASSISTIVE_DISCLAIMER
from .capture_models import CaptureMeasurements


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)


NonEmptyText = Annotated[str, Field(min_length=1, max_length=2000, pattern=r"\S")]
Percentage = Annotated[float, Field(ge=0, le=100)]
PositiveMeasurement = Annotated[float, Field(gt=0, le=10000)]


class TissueClass(str, Enum):
    GRANULACAO = "granulacao"
    ESFACELO_FIBRINA = "esfacelo_fibrina"
    NECROSE = "necrose"
    EPITELIZACAO = "epitelizacao"
    NAO_CLASSIFICADO_BAIXA_CONFIANCA = "nao_classificado_baixa_confianca"


class TissueComposition(StrictModel):
    """Percentages use wound-bed ROI pixels, including abstentions, as denominator.

    Edges and perilesional skin are contextual zones, not additional tissue pixels.
    The caller must retain the bed mask/denominator with segmentation provenance.
    """

    granulacao: Percentage
    esfacelo_fibrina: Percentage
    necrose: Percentage
    epitelizacao: Percentage
    nao_classificado_baixa_confianca: Percentage

    @model_validator(mode="after")
    def validate_total(self) -> TissueComposition:
        if not isclose(sum(self.model_dump().values()), 100.0, abs_tol=0.02):
            raise ValueError("Os cinco percentuais devem somar 100% da ROI.")
        return self


class ClinicalRole(str, Enum):
    ENFERMEIRO = "Enfermeiro"
    MEDICO = "Médico"
    ESTOMATERAPEUTA = "Estomaterapeuta"


class ProfessionalReview(StrictModel):
    reviewer_id: UUID
    role: ClinicalRole
    reviewed_at: AwareDatetime
    affirmed_by_professional: Literal[True]


class CEAPClassification(StrictModel):
    clinical: Literal["C0", "C1", "C2", "C2r", "C3", "C4a", "C4b", "C4c", "C5", "C6", "C6r"]
    symptomatic: bool | None = None
    etiology: Annotated[tuple[Literal["Ec", "Ep", "Es", "Esi", "Ese", "En"], ...], Field(min_length=1)]
    anatomy: Annotated[tuple[Literal["As", "Ad", "Ap", "An"], ...], Field(min_length=1)]
    pathophysiology: Annotated[tuple[Literal["Pr", "Po", "Pr,o", "Pn"], ...], Field(min_length=1)]
    review: ProfessionalReview


class WIfIClassification(StrictModel):
    """Store the three professional grades, without computing a risk/stage."""

    wound: Annotated[int, Field(strict=True, ge=0, le=3)]
    ischemia: Annotated[int, Field(strict=True, ge=0, le=3)]
    foot_infection: Annotated[int, Field(strict=True, ge=0, le=3)]
    review: ProfessionalReview


class FontaineClassification(StrictModel):
    stage: Literal["I", "IIa", "IIb", "III", "IV"]
    review: ProfessionalReview


class LPPClassification(StrictModel):
    stage: Literal["estagio_1", "estagio_2", "estagio_3", "estagio_4", "nao_classificavel", "lesao_tissular_profunda"]
    depth_confirmed_in_person: bool = False
    deep_structure_exposure: tuple[Literal["fascia", "musculo", "tendao", "cartilagem", "osso"], ...] = ()
    review: ProfessionalReview

    @model_validator(mode="after")
    def require_exam_for_deep_stages(self) -> LPPClassification:
        if self.stage in {"estagio_3", "estagio_4"} and not self.depth_confirmed_in_person:
            raise ValueError("Estágios 3 e 4 requerem profundidade confirmada em exame presencial.")
        if self.stage == "estagio_4" and not self.deep_structure_exposure:
            raise ValueError("Registre as estruturas profundas identificadas pelo profissional.")
        if self.stage == "estagio_3" and self.deep_structure_exposure:
            raise ValueError("Revisar a coerência do estágio com as estruturas profundas registradas.")
        return self


class ClinicalClassifications(StrictModel):
    ceap: CEAPClassification | None = None
    wifi: WIfIClassification | None = None
    fontaine: FontaineClassification | None = None
    lpp: LPPClassification | None = None


class PatientReference(StrictModel):
    """RC01a: pseudonym is not anonymization; protect the linkage separately."""

    patient_id: UUID
    pseudonym: Annotated[str, Field(pattern=r"^pt_[A-Za-z0-9_-]{8,64}$")]


class RelevantHistory(StrictModel):
    """RC02a: only relevant professional observations, no identity fields."""

    comorbidities: tuple[NonEmptyText, ...] = ()
    recurrence: bool | None = None
    wound_duration_days: Annotated[int, Field(strict=True, ge=0, le=100000)] | None = None
    context: NonEmptyText


class AnatomicalLocation(StrictModel):
    """RC03a. Use the institution's terminology; no localization inference."""

    region: Annotated[str, Field(min_length=1, max_length=160, pattern=r"\S")]
    laterality: Literal["direita", "esquerda", "bilateral", "mediana", "nao_aplicavel", "nao_informada"]


class WoundType(str, Enum):
    PRESSURE_INJURY = "lesao_por_pressao"
    SURGICAL = "ferida_cirurgica"
    VENOUS = "ulcera_venosa"
    ARTERIAL = "ulcera_arterial"
    DIABETIC_FOOT = "pe_diabetico"
    MIXED = "mista"
    OTHER = "outra"
    UNDETERMINED = "nao_determinada"


class WoundDimensions(StrictModel):
    """RC05a: missing measurements remain missing, never estimated as zero."""

    length_cm: PositiveMeasurement | None = None
    width_cm: PositiveMeasurement | None = None
    depth_cm: Annotated[float, Field(ge=0, le=100)] | None = None
    area_cm2: PositiveMeasurement | None = None
    method: Literal["manual_com_escala", "assistida_com_escala", "nao_mensuravel"]
    unavailable_reason: NonEmptyText | None = None

    @model_validator(mode="after")
    def validate_measurement(self) -> WoundDimensions:
        if self.method == "nao_mensuravel":
            if self.unavailable_reason is None:
                raise ValueError("Registre o motivo da ausência de medidas.")
            if any(value is not None for value in (self.length_cm, self.width_cm, self.depth_cm, self.area_cm2)):
                raise ValueError("Medidas indisponíveis não podem conter valores.")
        elif self.length_cm is None or self.width_cm is None:
            raise ValueError("Comprimento e largura são necessários para medição com escala.")
        return self


class InfectionSign(str, Enum):
    ODOR = "odor"
    ERYTHEMA = "rubor"
    WARMTH = "calor"
    INCREASED_PAIN = "dor_aumentada"
    DISCHARGE = "secrecao"
    WORSENING = "piora_visual"
    EDEMA = "edema"
    FEVER = "febre"


class Exudate(StrictModel):
    """RC08a: quantity, odor and consistency require professional observation."""

    amount: Literal["ausente", "pequeno", "moderado", "grande", "nao_avaliado"]
    appearance: Literal[
        "seroso", "serossanguinolento", "sanguinolento", "purulento", "outro", "nao_aplicavel", "nao_avaliado"
    ]
    odor_observed: bool | None = None


class PainAssessment(StrictModel):
    intensity: Annotated[int, Field(strict=True, ge=0, le=10)]
    source: Literal["relato_do_paciente", "avaliacao_profissional"]
    scale: Literal["numerica_0_10"] = "numerica_0_10"


class WoundEdge(str, Enum):
    DEFINED = "definidas"
    ATTACHED = "aderidas"
    DETACHED = "descoladas"
    MACERATED = "maceradas"
    EPITHELIALIZING = "epitelizadas"
    HYPERKERATOTIC = "hiperqueratosicas"
    IRREGULAR = "irregulares"
    NOT_EVALUATED = "nao_avaliadas"


class PerilesionalFinding(str, Enum):
    INTACT = "integra"
    HYPEREMIA = "hiperemia"
    EDEMA = "edema"
    MACERATION = "maceracao"
    INDURATION = "induracao"
    DRYNESS = "ressecamento"
    SCALING = "descamacao"
    IRRITATION = "irritacao"
    PIGMENTATION_CHANGE = "alteracao_pigmentacao"
    NOT_EVALUATED = "nao_avaliada"


class ResearchGovernance(StrictModel):
    """An approval reference records governance; it does not grant authorization."""

    ethics_approval_reference: NonEmptyText
    informed_consent_reference: NonEmptyText
    approved_at: AwareDatetime
    permitted_purpose: NonEmptyText


class PhotoConsent(StrictModel):
    consent_id: UUID
    recorded_at: AwareDatetime
    capture_authorized: Literal[True]
    care_use_authorized: Literal[True]
    external_processing_authorized: bool = False
    research_use_authorized: bool = False
    research_governance: ResearchGovernance | None = None

    @model_validator(mode="after")
    def require_research_governance(self) -> PhotoConsent:
        if self.research_use_authorized and self.research_governance is None:
            raise ValueError("Pesquisa com dados reais requer governança, CEP e TCLE registrados.")
        return self


class ImageRecord(StrictModel):
    """RC12a/RN04/RN05: opaque storage reference, never a signed or public URL."""

    image_id: UUID
    patient_id: UUID
    wound_id: UUID
    assessment_id: UUID
    captured_at: AwareDatetime
    captured_by: UUID
    purpose: Literal["acompanhamento_assistencial", "pesquisa_aprovada"]
    consent: PhotoConsent
    content_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    exif_removed: Literal[True]
    scale_present: bool = False
    capture_protocol: CaptureMeasurements | None = None
    capture_status: Literal["aceito", "indeterminado"] | None = None
    debridement_phase: Literal["pre_desbridamento", "pos_desbridamento", "nao_aplicavel", "desconhecido"] = (
        "desconhecido"
    )

    @model_validator(mode="after")
    def validate_purpose(self) -> ImageRecord:
        if self.purpose == "pesquisa_aprovada" and not self.consent.research_use_authorized:
            raise ValueError("Finalidade de pesquisa exige consentimento específico.")
        if self.consent.recorded_at > self.captured_at:
            raise ValueError("O consentimento deve preceder a captura.")
        protocol = self.capture_protocol
        if protocol is None:
            if self.capture_status is not None:
                raise ValueError("O estado de captura requer protocolo registrado.")
        else:
            if self.capture_status is None:
                raise ValueError("Registre o estado aceito ou indeterminado do protocolo de captura.")
            if not all(
                value is True
                for value in (
                    protocol.consent_to_capture,
                    protocol.privacy_checked,
                    protocol.identifying_exif_removed,
                )
            ):
                raise ValueError("O protocolo deve confirmar consentimento, privacidade e remoção de EXIF.")
            if protocol.scale_present is not None and protocol.scale_present != self.scale_present:
                raise ValueError("A presença da escala deve ser consistente com o protocolo de captura.")
            if protocol.scale_next_to_wound is True and not self.scale_present:
                raise ValueError("A posição da escala não pode ser confirmada quando não há escala no registro.")
            if self.capture_status == "aceito" and any(value is None for value in protocol.model_dump().values()):
                raise ValueError("Protocolo com medidas ou confirmações ausentes deve permanecer indeterminado.")
        return self


class TemporalEvolution(StrictModel):
    """RC13b: baseline explicitly represents the first available assessment."""

    baseline: bool
    previous_assessment_id: UUID | None = None
    observations: NonEmptyText

    @model_validator(mode="after")
    def validate_baseline(self) -> TemporalEvolution:
        if self.baseline != (self.previous_assessment_id is None):
            raise ValueError("Evolução requer registro anterior; avaliação inicial não pode referenciá-lo.")
        return self


class CarePlan(StrictModel):
    """RC16b: documentary record of a human decision, not a recommendation."""

    applicable: bool
    procedures: tuple[NonEmptyText, ...] = ()
    dressing: NonEmptyText | None = None
    therapy: NonEmptyText | None = None
    supplies: tuple[NonEmptyText, ...] = ()
    continuity_guidance: NonEmptyText
    review: ProfessionalReview


class DeviceAssociation(StrictModel):
    """Device-related injury metadata; mucosal injuries do not receive LPP stages."""

    device_type: NonEmptyText
    contact_region: NonEmptyText
    mucosal_contact: bool
    use_duration_hours: Annotated[float, Field(ge=0, le=100000)] | None = None
    review: ProfessionalReview


class PerfusionAssessment(StrictModel):
    """In-person measurements entered by a professional; no computed ischemia grade."""

    ankle_brachial_index: Annotated[float, Field(ge=0, le=3)] | None = None
    ankle_pressure_mmhg: Annotated[float, Field(ge=0, le=400)] | None = None
    toe_pressure_mmhg: Annotated[float, Field(ge=0, le=400)] | None = None
    transcutaneous_oxygen_mmhg: Annotated[float, Field(ge=0, le=400)] | None = None
    observations: NonEmptyText
    review: ProfessionalReview


class NeuropathyAssessment(StrictModel):
    protective_sensation: Literal["preservada", "reduzida", "ausente", "nao_avaliada"]
    examination_method: NonEmptyText
    observations: NonEmptyText
    review: ProfessionalReview


class ClinicalAssessment(StrictModel):
    """RC01a–RC16b. Values are professional records, never autonomous output."""

    assessment_id: UUID = Field(default_factory=uuid4)
    patient: PatientReference
    wound_id: UUID
    assessed_at: AwareDatetime
    professional_id: UUID
    history: RelevantHistory
    anatomical_location: AnatomicalLocation
    wound_type: WoundType
    dimensions: WoundDimensions
    predominant_tissue: TissueClass
    tissue_composition: TissueComposition | None = None
    infection_signs: tuple[InfectionSign, ...]
    exudate: Exudate
    pain: PainAssessment | None = None
    edges: Annotated[tuple[WoundEdge, ...], Field(min_length=1)]
    perilesional_skin: Annotated[tuple[PerilesionalFinding, ...], Field(min_length=1)]
    images: Annotated[tuple[ImageRecord, ...], Field(min_length=1)]
    temporal_evolution: TemporalEvolution
    professional_observations: NonEmptyText
    clinical_report: NonEmptyText
    care_plan: CarePlan
    classifications: ClinicalClassifications | None = None
    device_association: DeviceAssociation | None = None
    perfusion: PerfusionAssessment | None = None
    neuropathy: NeuropathyAssessment | None = None
    review: ProfessionalReview
    disclaimer: str = Field(default=ASSISTIVE_DISCLAIMER, json_schema_extra={"const": ASSISTIVE_DISCLAIMER})

    @field_validator("disclaimer")
    @classmethod
    def require_official_disclaimer(cls, value: str) -> str:
        if value != ASSISTIVE_DISCLAIMER:
            raise ValueError("O aviso assistivo oficial deve ser preservado integralmente.")
        return value

    @model_validator(mode="after")
    def validate_links_and_review(self) -> ClinicalAssessment:
        if self.review.reviewer_id != self.professional_id:
            raise ValueError("O registro deve indicar o profissional responsável pela revisão.")
        if self.review.reviewed_at < self.assessed_at:
            raise ValueError("A revisão não pode anteceder a avaliação.")
        if self.temporal_evolution.previous_assessment_id == self.assessment_id:
            raise ValueError("O registro anterior deve ser outra avaliação.")
        if len({image.image_id for image in self.images}) != len(self.images):
            raise ValueError("As referências de imagens devem ser únicas.")
        for image in self.images:
            if (image.patient_id, image.wound_id, image.assessment_id) != (
                self.patient.patient_id,
                self.wound_id,
                self.assessment_id,
            ):
                raise ValueError("A imagem deve pertencer ao paciente, ferida e avaliação deste registro.")
            if image.captured_at > self.review.reviewed_at:
                raise ValueError("A imagem deve existir antes da revisão do registro.")
        if self.classifications is not None:
            if self.device_association and self.device_association.mucosal_contact and self.classifications.lpp:
                raise ValueError("Lesão de mucosa associada a dispositivo não recebe estágio LPP.")
            if self.classifications.lpp is not None and self.wound_type != WoundType.PRESSURE_INJURY:
                raise ValueError("Estadiamento LPP aplica-se apenas a lesão por pressão.")
            for classification in (
                self.classifications.ceap,
                self.classifications.wifi,
                self.classifications.fontaine,
                self.classifications.lpp,
            ):
                if classification and classification.review.reviewed_at > self.review.reviewed_at:
                    raise ValueError("A classificação deve ter sido revista antes do fechamento do registro.")
        for observation in (self.device_association, self.perfusion, self.neuropathy, self.care_plan):
            if observation and observation.review.reviewed_at > self.review.reviewed_at:
                raise ValueError("Observações profissionais devem preceder o fechamento do registro.")
        return self
