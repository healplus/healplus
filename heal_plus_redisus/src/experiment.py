"""Fail-closed dataset governance, patient-group splits and frozen manifests.

Manifests contain technical inventory and reviewed governance references only.
Do not put patient records, names, clinical narratives or credentials in any
field. Technical key/value checks reduce accidental misuse but cannot identify
all sensitive information encoded as an otherwise valid string. Institutional
privacy review remains necessary before freezing or sharing a real manifest.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import random
import re
from pathlib import Path
from typing import Literal
from uuid import UUID

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False, revalidate_instances="always")


class DatasetGovernance(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=80)
    source: str = Field(min_length=1, max_length=500)
    license: str = Field(min_length=1, max_length=100)
    license_reviewed: StrictBool
    purpose: Literal["academic_research"] = "academic_research"
    kind: Literal["synthetic", "public", "clinical"]
    privacy_reviewed: StrictBool
    ethics_approval_reference: str | None = Field(default=None, max_length=120)
    consent_documented: StrictBool = False
    data_management_plan: str = Field(min_length=1, max_length=1500)
    risks_documented: StrictBool

    @model_validator(mode="after")
    def check_governance(self) -> "DatasetGovernance":
        if not self.license_reviewed or not self.privacy_reviewed or not self.risks_documented:
            raise ValueError("Licença, privacidade e riscos devem ser revisados antes do experimento.")
        if self.license.lower() in {"unknown", "desconhecida", "pending", "a confirmar"}:
            raise ValueError("Confirme a licença do conjunto de dados.")
        if self.kind == "clinical" and (not self.ethics_approval_reference or not self.consent_documented):
            raise ValueError("Dados clínicos de pesquisa exigem referência CEP e TCLE documentado.")
        return self


class DatasetItem(StrictModel):
    image_id: UUID
    patient_group: UUID
    split: Literal["train", "validation", "test"]
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    width: StrictInt = Field(ge=16, le=12000000)
    height: StrictInt = Field(ge=16, le=12000000)
    skin_tone: Literal["claro", "intermediario", "escuro_retinto", "desconhecido"]

    @model_validator(mode="after")
    def bounded_pixels(self) -> "DatasetItem":
        if self.width * self.height > 12_000_000:
            raise ValueError("Imagem excede 12 megapixels.")
        return self


class ModelManifest(StrictModel):
    architecture: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=120)
    checkpoint_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    status: Literal["unavailable", "experimental", "validated"]
    validation_reference: str | None = None
    hyperparameters: dict[str, float | int | str | bool] = Field(default_factory=dict)

    @field_validator("hyperparameters", mode="before")
    @classmethod
    def technical_parameters_only(cls, values: object) -> object:
        if not isinstance(values, dict):
            raise ValueError("Hiperparâmetros devem ser um objeto técnico de valores escalares.")
        forbidden = {
            "apikey",
            "token",
            "accesstoken",
            "refreshtoken",
            "password",
            "secret",
            "credential",
            "patientname",
            "patientid",
            "cpf",
            "mrn",
            "prontuario",
            "clinicalnote",
        }
        for key, value in values.items():
            if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,79}", key):
                raise ValueError("Use chaves técnicas curtas nos hiperparâmetros.")
            normalized = re.sub(r"[^a-z0-9]", "", key.casefold())
            if normalized in forbidden or normalized.endswith(
                (
                    "apikey",
                    "accesstoken",
                    "refreshtoken",
                    "password",
                    "secret",
                    "credential",
                    "patientname",
                    "patientid",
                    "prontuario",
                    "clinicalnote",
                )
            ):
                raise ValueError("Credenciais e identificadores pessoais não pertencem ao manifesto.")
            if isinstance(value, str) and (
                not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:+/-]{0,119}", value)
                or value.casefold() in {"nan", "inf", "infinity", "+inf", "-inf"}
                or value.startswith(("sk-", "sk_"))
            ):
                raise ValueError(
                    "Strings de hiperparâmetros devem ser categorias técnicas curtas, sem texto clínico ou credenciais."
                )
            if type(value) not in {float, int, str, bool}:
                raise ValueError("Hiperparâmetros admitem somente escalares técnicos.")
        return values

    @model_validator(mode="after")
    def verify_status(self) -> "ModelManifest":
        if self.status == "unavailable" and (self.checkpoint_sha256 or self.validation_reference):
            raise ValueError("Modelo indisponível não deve declarar pesos ou validação disponíveis.")
        if (
            self.version.strip().casefold() in {"untrained", "nao_treinado", "não_treinado"}
            and self.status != "unavailable"
        ):
            raise ValueError("Modelo não treinado deve permanecer indisponível.")
        if self.status != "unavailable" and not self.checkpoint_sha256:
            raise ValueError("Pesos de experimento exigem SHA-256.")
        if self.status == "validated" and not self.validation_reference:
            raise ValueError("Validação exige referência documental, não somente um indicador.")
        return self


class ExperimentManifest(StrictModel):
    schema_version: Literal[1] = 1
    experiment_id: UUID
    seed: StrictInt = Field(ge=0, le=2**32 - 1)
    dataset: DatasetGovernance
    model: ModelManifest
    detector: ModelManifest | None = None
    annotations_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    items: tuple[DatasetItem, ...] = ()
    code_revision: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def prevent_leakage(self) -> "ExperimentManifest":
        groups: dict[UUID, str] = {}
        hashes: dict[str, str] = {}
        ids = set()
        for item in self.items:
            if item.image_id in ids:
                raise ValueError("Identificador de imagem duplicado.")
            ids.add(item.image_id)
            if item.sha256 in hashes:
                raise ValueError("Conteúdo de imagem duplicado no inventário do experimento.")
            if item.patient_group in groups and groups[item.patient_group] != item.split:
                raise ValueError("Paciente aparece em mais de um split.")
            groups[item.patient_group] = item.split
            hashes[item.sha256] = item.split
        return self

    def require_evaluable(self) -> None:
        checked = ExperimentManifest.model_validate(self)
        if checked.model.status == "unavailable" or not checked.model.checkpoint_sha256:
            raise ValueError("Benchmark exige pesos disponíveis e identificados por SHA-256.")
        if not checked.items or not any(item.split == "test" for item in checked.items):
            raise ValueError("O manifesto precisa de imagens de teste antes de calcular desempenho.")
        if checked.dataset.kind != "synthetic":
            for split in {item.split for item in checked.items}:
                tones = {item.skin_tone for item in checked.items if item.split == split}
                if not {"claro", "intermediario", "escuro_retinto"} <= tones:
                    raise ValueError(
                        "Cada split fornecido exige representação dos três estratos de tom de pele antes do benchmark."
                    )


def load_manifest(path: str | Path) -> ExperimentManifest:
    return ExperimentManifest.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def seed_experiment(seed: int) -> None:
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("Seed deve ser um inteiro entre 0 e 2**32 - 1.")
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
    except ImportError:
        return
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False


def freeze_manifest(manifest: ExperimentManifest, path: str | Path) -> str:
    """Write once; the SHA covers dataset, split, weights, code and runtime."""
    manifest = ExperimentManifest.model_validate(manifest)
    runtime = {"python": platform.python_version(), "platform": platform.system()}
    source_hash = hashlib.sha256()
    package_root = Path(__file__).resolve().parents[1]
    for source in sorted(package_root.rglob("*.py")):
        source_hash.update(str(source.relative_to(package_root)).replace("\\", "/").encode("utf-8"))
        source_hash.update(b"\0" + source.read_bytes() + b"\0")
    decoder = package_root.parent / "src" / "image_quality" / "decoder.py"
    source_hash.update(b"shared/image_quality/decoder.py\0" + decoder.read_bytes())
    runtime["source_snapshot_sha256"] = source_hash.hexdigest()
    for package in (
        "numpy",
        "torch",
        "opencv-python",
        "opencv-python-headless",
        "pydantic",
        "Pillow",
        "scipy",
        "matplotlib",
        "PyYAML",
        "jsonschema",
        "ultralytics",
    ):
        try:
            runtime[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass
    payload = {"manifest": manifest.model_dump(mode="json"), "runtime": runtime}
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(data)
    return hashlib.sha256(data).hexdigest()
