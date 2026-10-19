"""Reproducible Sprint 1 → Sprint 2 research run with immutable inventory binding."""

from __future__ import annotations

import base64
import copy
from dataclasses import dataclass, field, replace
import hashlib
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence
from uuid import UUID, uuid4

import numpy as np

from .domain.rbac_audit import (
    Action,
    AuditEvent,
    AuditOutcome,
    AuditReason,
    AuditStore,
    DataClass,
    Principal,
    ResourceScope,
    authorize,
)
from .experiment import ExperimentManifest, freeze_manifest, seed_experiment
from .privacy import SanitizedImage
from .safety import ASSISTIVE_DISCLAIMER
from .sprint1_pipeline.cascade_evaluator import CascadeEvaluation, CascadeEvaluator
from .sprint1_pipeline.hybrid_segmenter import CONTEXT_FLAGS, ETIOLOGIES
from .sprint1_pipeline.report_sprint1 import export_experiment
from .sprint1_pipeline.roi_handler import ROI, ROIHandler


@dataclass(frozen=True)
class ExperimentCase:
    image_id: UUID
    image: SanitizedImage = field(repr=False)
    rois: tuple[ROI, ...]
    reference_bed_masks: Mapping[str, np.ndarray] = field(repr=False)
    context: Mapping[str, object]
    professional_bed_masks: Mapping[str, np.ndarray] | None = field(default=None, repr=False)
    reference_tissue_maps: Mapping[str, np.ndarray] | None = field(default=None, repr=False)


def _canonical_json(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
        "utf-8"
    )


def _technical_context(context: Mapping[str, object]) -> Mapping[str, object]:
    if set(context) - {"etiology", *CONTEXT_FLAGS}:
        raise ValueError("O snapshot admite somente etiologia e flags técnicas, sem texto clínico livre.")
    etiology = context.get("etiology")
    if not isinstance(etiology, str) or etiology not in ETIOLOGIES:
        raise ValueError("Informe etiologia profissional reconhecida ou explicitamente unknown.")
    result: dict[str, object] = {"etiology": etiology}
    for flag in CONTEXT_FLAGS:
        value = context.get(flag)
        if value is not None and type(value) is not bool:
            raise ValueError("Flags técnicas devem ser booleanas ou desconhecidas.")
        result[flag] = value
    return MappingProxyType(result)


def _array_snapshot(array: np.ndarray) -> dict[str, object]:
    """Portable deterministic pixels; no pickle, object arrays or ZIP timestamps."""
    raw = array.tobytes(order="C")
    boolean = array.dtype == np.bool_
    encoded = np.packbits(array.reshape(-1), bitorder="little").tobytes() if boolean else raw
    return {
        "shape": list(array.shape),
        "dtype": "bool" if boolean else "uint8",
        "encoding": "packbits-little-base64" if boolean else "raw-base64",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "data": base64.b64encode(encoded).decode("ascii"),
    }


def _copy_masks(
    masks: Mapping[str, np.ndarray] | None,
    rois: tuple[ROI, ...],
    shape: tuple[int, int],
    *,
    tissue: bool = False,
    complete: bool = True,
) -> Mapping[str, np.ndarray] | None:
    if masks is None:
        if complete:
            raise ValueError("Anotações de referência são obrigatórias para cada ROI.")
        return None
    identifiers = {roi.id for roi in rois}
    if (complete and set(masks) != identifiers) or not set(masks) <= identifiers:
        raise ValueError("As chaves das anotações devem corresponder às ROIs fornecidas.")
    copied = {}
    for key in sorted(masks):
        value = masks[key]
        expected_dtype = np.dtype(np.uint8 if tissue else np.bool_)
        if not isinstance(value, np.ndarray) or value.shape != shape or value.dtype != expected_dtype:
            raise ValueError("Máscaras devem coincidir com a imagem e usar bool ou uint8 conforme o tipo.")
        # Boolean storage can contain noncanonical nonzero bytes after a view
        # over raw uint8 data. Normalize truth values so packed snapshots decode
        # to the exact same canonical bytes used by inference and their hash.
        immutable = np.array(value if tissue else np.logical_and(value, True), copy=True, order="C")
        immutable.setflags(write=False)
        copied[key] = immutable
    return MappingProxyType(copied)


def _freeze_case(case: ExperimentCase, rgb: np.ndarray) -> ExperimentCase:
    pixels = np.array(rgb, copy=True, order="C")
    pixels.setflags(write=False)
    rois = tuple(
        ROI(roi.id, (roi.bbox[0], roi.bbox[1], roi.bbox[2], roi.bbox[3]), float(roi.confidence), roi.source)
        for roi in case.rois
    )
    ROIHandler().validate(pixels, rois)
    shape = (pixels.shape[0], pixels.shape[1])
    references = _copy_masks(case.reference_bed_masks, rois, shape)
    assert references is not None
    return ExperimentCase(
        case.image_id,
        replace(case.image, rgb=pixels),
        rois,
        references,
        _technical_context(case.context),
        _copy_masks(case.professional_bed_masks, rois, shape, complete=False),
        _copy_masks(
            case.reference_tissue_maps, rois, shape, tissue=True, complete=case.reference_tissue_maps is not None
        ),
    )


def _snapshot_case(case: ExperimentCase) -> dict[str, object]:
    def arrays(masks: Mapping[str, np.ndarray] | None) -> dict[str, object] | None:
        return None if masks is None else {key: _array_snapshot(masks[key]) for key in sorted(masks)}

    return {
        "image_id": str(case.image_id),
        "image_sha256": case.image.sha256,
        "dimensions": [case.image.height, case.image.width],
        "rois": [
            {"id": roi.id, "bbox": list(roi.bbox), "confidence": roi.confidence, "source": roi.source}
            for roi in case.rois
        ],
        "context": dict(case.context),
        "reference_bed_masks": arrays(case.reference_bed_masks),
        "professional_bed_masks": arrays(case.professional_bed_masks),
        "reference_tissue_maps": arrays(case.reference_tissue_maps),
    }


def _freeze_evaluator(evaluator: CascadeEvaluator) -> tuple[CascadeEvaluator, dict[str, object]]:
    """Copy technical scalar configuration; reviewed model weights stay loaded.

    The caller must not retrain or mutate the shared neural tensors during a run.
    Copying a loaded model's tensors would duplicate potentially large weights;
    provenance is separately bound to reviewed checkpoint hashes.
    """
    frozen = copy.copy(evaluator)
    frozen.segmenter = copy.copy(evaluator.segmenter)
    frozen.segmenter.roi_handler = copy.copy(evaluator.segmenter.roi_handler)
    backend = evaluator.segmenter.backend
    frozen.segmenter.backend = copy.copy(backend) if backend is not None else None
    frozen.detector = copy.copy(evaluator.detector)

    def finite(value: object, label: str) -> float:
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise ValueError("Configuração técnica deve conter números finitos: " + label)
        return float(value)

    segmenter: dict[str, object] = {
        "confidence_threshold": finite(frozen.segmenter.confidence_threshold, "confidence_threshold"),
        "entropy_threshold": finite(frozen.segmenter.entropy_threshold, "entropy_threshold"),
        "context_margin": finite(frozen.segmenter.roi_handler.context_margin, "context_margin"),
    }
    if (
        not 0 < frozen.segmenter.confidence_threshold <= 1
        or not 0 < frozen.segmenter.entropy_threshold <= 1
        or not 0 <= frozen.segmenter.roi_handler.context_margin <= 2
    ):
        raise ValueError("Limiares efetivos do segmentador estão fora dos limites técnicos.")
    backend_config = None
    if frozen.segmenter.backend is not None:
        backend = frozen.segmenter.backend
        names = tuple(backend.feature_names)
        if not names or not all(isinstance(name, str) and name and name.replace("_", "").isalnum() for name in names):
            raise ValueError("Nomes de features devem ser identificadores técnicos.")
        # Tuple detaches a caller-supplied mutable feature-name list.
        backend.feature_names = names
        backend_config = {
            "feature_names": list(names),
            "model_version": backend.model_version,
            "checkpoint_sha256": getattr(backend, "checkpoint_sha256", None),
        }
        if hasattr(backend, "max_side"):
            max_side = getattr(backend, "max_side")
            if type(max_side) is not int or not 32 <= max_side <= 2048:
                raise ValueError("Resolução efetiva do backend deve ser um inteiro entre 32 e 2048.")
            backend_config["max_side"] = max_side
    detector_config: dict[str, object] = {
        "implementation": type(frozen.detector).__module__ + "." + type(frozen.detector).__qualname__
    }
    for attribute in ("model_version", "checkpoint_sha256"):
        detector_config[attribute] = getattr(frozen.detector, attribute, None)
    if hasattr(frozen.detector, "confidence_threshold"):
        detector_threshold = finite(getattr(frozen.detector, "confidence_threshold"), "detector.confidence_threshold")
        if not 0 <= detector_threshold <= 1:
            raise ValueError("Confiança efetiva do detector deve estar entre zero e um.")
        detector_config["confidence_threshold"] = detector_threshold
    if hasattr(frozen.detector, "allowed_class_ids"):
        identifiers = tuple(getattr(frozen.detector, "allowed_class_ids"))
        if not identifiers or not all(type(value) is int and value >= 0 for value in identifiers):
            raise ValueError("Classes do detector devem ser inteiros não negativos.")
        setattr(frozen.detector, "allowed_class_ids", identifiers)
        detector_config["allowed_class_ids"] = list(identifiers)
    return frozen, {"segmenter": segmenter, "backend": backend_config, "detector": detector_config}


def run_experiment(
    principal: Principal,
    manifest: ExperimentManifest,
    cases: Sequence[ExperimentCase],
    evaluator: CascadeEvaluator,
    audit: AuditStore,
    output_dir: str | Path,
    *,
    synthetic_abstention: bool = False,
) -> tuple[CascadeEvaluation, ...]:
    """Evaluate exactly the frozen test split; never feed ground truth as input.

    Professional input masks are an explicit, separately recorded experimental
    intervention. Keep them absent when comparing contour predictors themselves.
    Manifest hashes bind outputs, source image bytes, exact annotations and the
    effective technical configuration. ``inputs.json`` uses deterministic
    base64/bitpack arrays, never pickle; it contains no clinical free text.
    """
    manifest = ExperimentManifest.model_validate(manifest.model_dump(mode="json"))
    if synthetic_abstention:
        if (
            manifest.dataset.kind != "synthetic"
            or manifest.model.status != "unavailable"
            or evaluator.segmenter.backend is not None
        ):
            raise ValueError("Demonstração de abstenção exige somente dados sintéticos e ausência de pesos.")
        if not manifest.items or not any(item.split == "test" for item in manifest.items):
            raise ValueError("A demonstração precisa de inventário sintético de teste.")
    else:
        manifest.require_evaluable()
    kind = {"synthetic": DataClass.SYNTHETIC, "public": DataClass.PUBLIC, "clinical": DataClass.DEIDENTIFIED}[
        manifest.dataset.kind
    ]
    scope = ResourceScope(
        tenant_id=principal.tenant_id,
        resource_id=manifest.experiment_id,
        data_class=kind,
        research_approved=manifest.dataset.kind == "clinical" and bool(manifest.dataset.ethics_approval_reference),
    )
    correlation = uuid4()
    authorize(principal, Action.RUN_EXPERIMENT, scope, audit=audit, correlation_id=correlation)
    inventory = {item.image_id: item for item in manifest.items if item.split == "test"}
    if {case.image_id for case in cases} != set(inventory) or len(cases) != len(inventory):
        raise ValueError("Os casos devem corresponder exatamente ao split de teste congelado.")
    frozen_cases = []
    for case in sorted(cases, key=lambda case: str(case.image_id)):
        item = inventory[case.image_id]
        if (
            not case.image.metadata_removed
            or hashlib.sha256(case.image.content).hexdigest() != item.sha256
            or case.image.sha256 != item.sha256
        ):
            raise ValueError("Integridade ou remoção de metadados não corresponde ao manifesto.")
        if (case.image.width, case.image.height) != (item.width, item.height):
            raise ValueError("Resolução do caso difere do inventário.")
        # Derive inference pixels from the hashed bytes, not a separately supplied array.
        import io
        from PIL import Image

        with Image.open(io.BytesIO(case.image.content)) as image:
            pixels = np.asarray(image.convert("RGB"))
            if (
                image.info
                or image.getexif()
                or image.size != (item.width, item.height)
                or not np.array_equal(pixels, case.image.rgb)
            ):
                raise ValueError("Pixels ou metadados do caso divergem dos bytes inventariados.")
            frozen_cases.append(_freeze_case(case, pixels))
    cases = tuple(frozen_cases)
    evaluator, effective_configuration = _freeze_evaluator(evaluator)
    backend = evaluator.segmenter.backend
    if manifest.model.status == "unavailable":
        if backend is not None:
            raise ValueError("O manifesto registra ausência de pesos, mas um backend foi fornecido.")
    elif (
        backend is None
        or getattr(backend, "checkpoint_sha256", None) != manifest.model.checkpoint_sha256
        or backend.model_version != manifest.model.version
    ):
        raise ValueError("Versão ou pesos do segmentador diferem do manifesto.")
    detector_manifest = getattr(manifest, "detector", None)
    if not synthetic_abstention and (detector_manifest is None or detector_manifest.status == "unavailable"):
        raise ValueError("Comparação em cascata exige manifesto próprio dos pesos do detector.")
    if detector_manifest and detector_manifest.status != "unavailable":
        if (
            getattr(evaluator.detector, "checkpoint_sha256", None) != detector_manifest.checkpoint_sha256
            or getattr(evaluator.detector, "model_version", None) != detector_manifest.version
        ):
            raise ValueError("A versão ou os pesos do detector diferem do manifesto.")
    inputs = {
        "schema_version": 1,
        "configuration": effective_configuration,
        "cases": [_snapshot_case(case) for case in cases],
    }
    snapshot = _canonical_json(inputs)
    annotations_digest = hashlib.sha256(snapshot).hexdigest()
    if manifest.annotations_sha256 is not None and manifest.annotations_sha256 != annotations_digest:
        raise ValueError("Anotações ou configuração efetiva diferem do snapshot declarado no manifesto.")
    manifest = manifest.model_copy(update={"annotations_sha256": annotations_digest})
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    with (output / "inputs.json").open("xb") as stream:
        stream.write(snapshot)
    digest = freeze_manifest(manifest, output / "manifest.json")
    seed_experiment(manifest.seed)
    try:
        evaluations = tuple(
            evaluator.evaluate(
                str(case.image_id),
                case.image.rgb,
                list(case.rois),
                case.reference_bed_masks,
                context=case.context,
                professional_bed_masks=case.professional_bed_masks,
                reference_tissue_maps=case.reference_tissue_maps,
                dataset_name=manifest.dataset.name,
                dataset_license=manifest.dataset.license,
            )
            for case in cases
        )
        export_experiment(evaluations, {str(case.image_id): case.image.rgb for case in cases}, output)
        artifacts = {
            str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(output.rglob("*"))
            if path.is_file()
        }
        run = {
            "experiment_id": str(manifest.experiment_id),
            "manifest_sha256": digest,
            "annotations_sha256": annotations_digest,
            "model_version": manifest.model.version,
            "model_status": manifest.model.status,
            "dataset_version": manifest.dataset.version,
            "split": "test",
            "seed": manifest.seed,
            "synthetic_abstention_only": synthetic_abstention,
            "professional_input_masks_supplied": any(case.professional_bed_masks is not None for case in cases),
            "artifacts_sha256": artifacts,
            "disclaimer": ASSISTIVE_DISCLAIMER,
        }
        (output / "experiment_run.json").write_text(
            json.dumps(run, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
        )
    except Exception:
        audit.append(
            AuditEvent(
                actor_id=principal.user_id,
                tenant_id=principal.tenant_id,
                action=Action.RUN_EXPERIMENT,
                outcome=AuditOutcome.FAILED,
                reason=AuditReason.OPERATION_FAILED,
                correlation_id=correlation,
            )
        )
        raise
    audit.append(
        AuditEvent(
            actor_id=principal.user_id,
            tenant_id=principal.tenant_id,
            action=Action.RUN_EXPERIMENT,
            outcome=AuditOutcome.COMPLETED,
            reason=AuditReason.OPERATION_COMPLETED,
            correlation_id=correlation,
        )
    )
    return evaluations
