"""Exact annotation custody and stable technical input snapshots; synthetic only."""

import base64
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest

from heal_plus_redisus.examples.synthetic_demo import geometry, NoDetector
from heal_plus_redisus.src.domain.rbac_audit import AuditStore, Principal, Role
from heal_plus_redisus.src.experiment import ExperimentManifest, load_manifest
from heal_plus_redisus.src import experiment_runner as runner
from heal_plus_redisus.src.experiment_runner import ExperimentCase, run_experiment
from heal_plus_redisus.src.privacy import sanitize_upload
from heal_plus_redisus.src.sprint1_pipeline.cascade_evaluator import CascadeEvaluator
from heal_plus_redisus.src.sprint1_pipeline.hybrid_segmenter import HybridSegmenter
from heal_plus_redisus.src.sprint1_pipeline.roi_handler import ROI


@pytest.fixture
def setup(tmp_path, monkeypatch):
    raw, bed = geometry()
    image = sanitize_upload(raw, "image/png", consent=True, privacy_reviewed=True)
    image_id = uuid4()
    data = load_manifest(Path(__file__).resolve().parents[1] / "config" / "experiment_manifest.yaml").model_dump(
        mode="json"
    )
    data["items"] = [
        {
            "image_id": str(image_id),
            "patient_group": str(uuid4()),
            "split": "test",
            "sha256": image.sha256,
            "width": image.width,
            "height": image.height,
            "skin_tone": "desconhecido",
        }
    ]
    manifest = ExperimentManifest.model_validate(data)
    roi = ROI("one", (40, 30, 105, 90))
    tissue = np.full(bed.shape, 255, dtype=np.uint8)
    tissue[bed] = 4
    case = ExperimentCase(
        image_id, image, (roi,), {roi.id: bed}, {"etiology": "unknown"}, {roi.id: bed.copy()}, {roi.id: tissue}
    )
    actor = Principal(user_id=uuid4(), tenant_id=uuid4(), role=Role.PESQUISADOR, authenticated=True)
    audit = AuditStore(tmp_path / "audit.db", b"synthetic-input-custody-key-1234567")
    evaluator = CascadeEvaluator(HybridSegmenter(), NoDetector())
    # These cases target snapshot custody. Full real report export has its own
    # integration test; avoid producing many equivalent panels for every edge.
    monkeypatch.setattr(
        runner,
        "export_experiment",
        lambda evaluations, images, output: (output / "metrics.json").write_text("{}", encoding="utf-8"),
    )
    yield actor, manifest, case, evaluator, audit
    audit.close()


def execute(setup, output, case=None, manifest=None, evaluator=None):
    actor, original_manifest, original_case, original_evaluator, audit = setup
    values = run_experiment(
        actor,
        manifest or original_manifest,
        [case or original_case],
        evaluator or original_evaluator,
        audit,
        output,
        synthetic_abstention=True,
    )
    snapshot = json.loads((output / "inputs.json").read_text(encoding="utf-8"))
    run = json.loads((output / "experiment_run.json").read_text(encoding="utf-8"))
    return snapshot, run, values


def decode_array(record):
    raw = base64.b64decode(record["data"], validate=True)
    count = int(np.prod(record["shape"]))
    if record["encoding"] == "packbits-little-base64":
        result = np.unpackbits(np.frombuffer(raw, dtype=np.uint8), bitorder="little", count=count).astype(bool)
    else:
        assert record["encoding"] == "raw-base64" and record["dtype"] == "uint8"
        result = np.frombuffer(raw, dtype=np.uint8)
    result = result.reshape(record["shape"])
    assert hashlib.sha256(result.tobytes(order="C")).hexdigest() == record["sha256"]
    return result


def test_identical_inputs_have_stable_digest_linked_to_frozen_manifest_and_artifacts(setup, tmp_path):
    snapshot, run, values = execute(setup, tmp_path / "one")
    snapshot2, run2, _ = execute(setup, tmp_path / "two")
    assert snapshot == snapshot2
    assert run["annotations_sha256"] == run2["annotations_sha256"]
    assert hashlib.sha256((tmp_path / "one" / "inputs.json").read_bytes()).hexdigest() == run["annotations_sha256"]
    frozen = json.loads((tmp_path / "one" / "manifest.json").read_text(encoding="utf-8"))
    assert frozen["manifest"]["annotations_sha256"] == run["annotations_sha256"]
    assert run["artifacts_sha256"]["inputs.json"] == run["annotations_sha256"]
    assert run["synthetic_abstention_only"]
    assert values[0].manual_results[0].status == "abstained_no_validated_model"


@pytest.mark.parametrize("change", ["roi", "reference_bed", "reference_tissue", "professional_bed", "context"])
def test_roi_ground_truth_professional_input_or_context_changes_digest(setup, tmp_path, change):
    _, baseline, _ = execute(setup, tmp_path / "baseline")
    case = setup[2]
    if change == "roi":
        case = replace(case, rois=(ROI("one", (39, 30, 105, 90)),))
    elif change == "context":
        case = replace(case, context={"etiology": "other", "recent_debridement": True})
    else:
        field = {
            "reference_bed": "reference_bed_masks",
            "reference_tissue": "reference_tissue_maps",
            "professional_bed": "professional_bed_masks",
        }[change]
        copied = dict(getattr(case, field))
        copied["one"] = copied["one"].copy()
        copied["one"][40, 50] = 0 if change == "reference_tissue" else False
        case = replace(case, **{field: copied})
    _, changed, _ = execute(setup, tmp_path / "changed", case=case)
    assert baseline["annotations_sha256"] != changed["annotations_sha256"]


def test_snapshot_contains_exact_typed_annotations_and_effective_configuration(setup, tmp_path):
    snapshot, _, _ = execute(setup, tmp_path / "exact")
    case = setup[2]
    stored = snapshot["cases"][0]
    assert stored["rois"] == [{"id": "one", "bbox": [40, 30, 105, 90], "confidence": 1.0, "source": "manual"}]
    for key in ("reference_bed_masks", "reference_tissue_maps", "professional_bed_masks"):
        assert np.array_equal(decode_array(stored[key]["one"]), getattr(case, key)["one"])
    assert stored["context"] == {
        "etiology": "unknown",
        "suspected_blood": None,
        "residual_dressing": None,
        "recent_debridement": None,
    }
    configuration = snapshot["configuration"]
    assert configuration["segmenter"] == {
        "confidence_threshold": 0.65,
        "entropy_threshold": 0.65,
        "context_margin": 0.25,
    }
    assert configuration["backend"] is None
    assert configuration["detector"]["implementation"].endswith("NoDetector")


def test_mutation_after_snapshot_cannot_change_evaluated_copies(setup, tmp_path, monkeypatch):
    case, evaluator = setup[2], setup[3]
    original_freeze = runner.freeze_manifest
    original_bed = case.reference_bed_masks["one"].copy()
    original_tissue = case.reference_tissue_maps["one"].copy()

    def freeze_and_mutate(manifest, path):
        digest = original_freeze(manifest, path)
        case.reference_bed_masks["one"][:] = False
        case.reference_tissue_maps["one"][:] = 0
        case.professional_bed_masks["one"][:] = False
        case.context["etiology"] = "other"
        case.image.rgb[:] = 0
        evaluator.segmenter.confidence_threshold = 0.10
        evaluator.segmenter.roi_handler.context_margin = 1.5
        return digest

    monkeypatch.setattr(runner, "freeze_manifest", freeze_and_mutate)
    snapshot, _, results = execute(setup, tmp_path / "mutated")
    stored = snapshot["cases"][0]
    assert np.array_equal(decode_array(stored["reference_bed_masks"]["one"]), original_bed)
    assert np.array_equal(decode_array(stored["reference_tissue_maps"]["one"]), original_tissue)
    assert results[0].manual_results[0].bed_mask.sum() == original_bed.sum()
    assert results[0].manual_results[0].context_bbox == (23, 15, 122, 105)


def test_missing_professional_input_is_not_replaced_with_reference_bed(setup, tmp_path):
    case = replace(setup[2], professional_bed_masks=None)
    snapshot, run, values = execute(setup, tmp_path / "no-professional-input", case=case)
    assert snapshot["cases"][0]["professional_bed_masks"] is None
    assert not run["professional_input_masks_supplied"]
    assert values[0].manual_results[0].bed_source == "unavailable"
    assert not values[0].manual_results[0].bed_mask.any()


@pytest.mark.parametrize(
    "context",
    [{"etiology": "unknown", "notes": "SYNTHETIC_FREE_TEXT"}, {"etiology": "unknown", "suspected_blood": "yes"}],
)
def test_snapshot_rejects_free_text_and_non_boolean_flags_before_persistence(setup, tmp_path, context):
    output = tmp_path / "rejected"
    with pytest.raises(ValueError):
        execute(setup, output, case=replace(setup[2], context=context))
    assert not output.exists()


def test_declared_annotation_hash_must_match_actual_inputs(setup, tmp_path):
    manifest = setup[1].model_copy(update={"annotations_sha256": "0" * 64})
    with pytest.raises(ValueError, match="snapshot"):
        execute(setup, tmp_path / "mismatch", manifest=manifest)


def test_effective_technical_configuration_changes_digest(setup, tmp_path):
    _, first, _ = execute(setup, tmp_path / "first")
    setup[3].segmenter.confidence_threshold = 0.75
    setup[3].segmenter.roi_handler.context_margin = 0.50
    snapshot, second, _ = execute(setup, tmp_path / "second")
    assert first["annotations_sha256"] != second["annotations_sha256"]
    assert snapshot["configuration"]["segmenter"]["confidence_threshold"] == 0.75


def test_backend_and_detector_effective_settings_are_detached_and_recorded():
    from heal_plus_redisus.src.sprint1_pipeline.hybrid_segmenter import FEATURE_NAMES

    class TechnicalBackend:
        feature_names = list(FEATURE_NAMES)
        model_version = "synthetic-fixture-v1"
        checkpoint_sha256 = "a" * 64
        max_side = 256

    class TechnicalDetector(NoDetector):
        confidence_threshold = 0.45
        allowed_class_ids = [0, 2]
        model_version = "synthetic-detector-v1"
        checkpoint_sha256 = "b" * 64

    evaluator = CascadeEvaluator(HybridSegmenter(backend=TechnicalBackend()), TechnicalDetector())
    frozen, configuration = runner._freeze_evaluator(evaluator)
    assert configuration["backend"]["feature_names"] == list(FEATURE_NAMES)
    assert configuration["backend"]["max_side"] == 256
    assert configuration["detector"]["confidence_threshold"] == 0.45
    assert configuration["detector"]["allowed_class_ids"] == [0, 2]
    assert configuration["detector"]["model_version"] == "synthetic-detector-v1"
    evaluator.segmenter.backend.max_side = 512
    evaluator.detector.allowed_class_ids.append(4)
    evaluator.detector.confidence_threshold = 0.95
    assert frozen.segmenter.backend.max_side == 256
    assert frozen.detector.allowed_class_ids == (0, 2)
    assert frozen.detector.confidence_threshold == 0.45


def test_detector_version_must_match_manifest_independently_of_weight_hash(setup, tmp_path):
    from heal_plus_redisus.src.sprint1_pipeline.hybrid_segmenter import FEATURE_NAMES

    class TechnicalBackend:
        feature_names = FEATURE_NAMES
        model_version = "synthetic-fixture-v1"
        checkpoint_sha256 = "a" * 64

    class TechnicalDetector(NoDetector):
        model_version = "different-version"
        checkpoint_sha256 = "b" * 64

    actor, original_manifest, case, _, audit = setup
    payload = original_manifest.model_dump(mode="json")
    payload["model"].update(version="synthetic-fixture-v1", status="experimental", checkpoint_sha256="a" * 64)
    payload["detector"] = {
        "architecture": "synthetic-detector",
        "version": "expected-version",
        "status": "experimental",
        "checkpoint_sha256": "b" * 64,
    }
    manifest = ExperimentManifest.model_validate(payload)
    evaluator = CascadeEvaluator(HybridSegmenter(backend=TechnicalBackend()), TechnicalDetector())
    with pytest.raises(ValueError, match="versão ou os pesos do detector"):
        run_experiment(actor, manifest, [case], evaluator, audit, tmp_path / "wrong-detector")
    assert not (tmp_path / "wrong-detector").exists()
