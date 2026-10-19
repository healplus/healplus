"""Source custody, role, and provenance checks for actual experiment orchestration."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from heal_plus_redisus.examples.synthetic_demo import geometry, NoDetector, run_demo
from heal_plus_redisus.src.domain.rbac_audit import AccessDenied, AuditStore, Principal, Role
from heal_plus_redisus.src.experiment import ExperimentManifest, load_manifest
from heal_plus_redisus.src.experiment_runner import ExperimentCase, run_experiment
from heal_plus_redisus.src.privacy import sanitize_upload
from heal_plus_redisus.src.safety import ASSISTIVE_DISCLAIMER
from heal_plus_redisus.src.sprint1_pipeline.cascade_evaluator import CascadeEvaluator
from heal_plus_redisus.src.sprint1_pipeline.hybrid_segmenter import HybridSegmenter
from heal_plus_redisus.src.sprint1_pipeline.roi_handler import ROI


@pytest.fixture
def experiment(tmp_path):
    raw, mask = geometry()
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
    case = ExperimentCase(image_id, image, (ROI("one", (40, 30, 105, 90)),), {"one": mask}, {"etiology": "unknown"})
    actor = Principal(user_id=uuid4(), tenant_id=uuid4(), role=Role.PESQUISADOR, authenticated=True)
    evaluator = CascadeEvaluator(HybridSegmenter(), NoDetector())
    audit = AuditStore(tmp_path / "audit.db", b"synthetic-experiment-key-123456789")
    yield actor, manifest, case, evaluator, audit
    audit.close()


def test_real_benchmark_does_not_accept_unavailable_model(experiment, tmp_path):
    actor, manifest, case, evaluator, audit = experiment
    with pytest.raises(ValueError, match="pesos"):
        run_experiment(actor, manifest, [case], evaluator, audit, tmp_path / "run")
    assert not (tmp_path / "run").exists()


def test_experiment_inventory_and_pixels_cannot_be_replaced(experiment, tmp_path):
    actor, manifest, case, evaluator, audit = experiment
    with pytest.raises(ValueError, match="split"):
        run_experiment(
            actor,
            manifest,
            [replace(case, image_id=uuid4())],
            evaluator,
            audit,
            tmp_path / "bad",
            synthetic_abstention=True,
        )
    changed = case.image.rgb.copy()
    changed[0, 0] = 0
    replacement = replace(case, image=replace(case.image, rgb=changed))
    with pytest.raises(ValueError, match="Pixels"):
        run_experiment(
            actor, manifest, [replacement], evaluator, audit, tmp_path / "tampered", synthetic_abstention=True
        )


def test_experiment_unauthenticated_or_patient_actor_is_denied(experiment, tmp_path):
    actor, manifest, case, evaluator, audit = experiment
    for changes in ({"authenticated": False}, {"role": Role.PACIENTE}):
        with pytest.raises(AccessDenied):
            run_experiment(
                actor.model_copy(update=changes),
                manifest,
                [case],
                evaluator,
                audit,
                tmp_path / "denied",
                synthetic_abstention=True,
            )
    assert not (tmp_path / "denied").exists()


def test_synthetic_demo_integrates_actual_service_fhir_reports_and_manifest(tmp_path):
    output = tmp_path / "demo"
    result = run_demo(output)
    assert result["synthetic_only"] and result["bundle_resources"] == 7
    run = json.loads((output / "experiment" / "experiment_run.json").read_text(encoding="utf-8"))
    assert run["synthetic_abstention_only"]
    assert run["manifest_sha256"] == hashlib.sha256((output / "experiment" / "manifest.json").read_bytes()).hexdigest()
    for path, expected in run["artifacts_sha256"].items():
        assert hashlib.sha256((output / "experiment" / path).read_bytes()).hexdigest() == expected
    metrics = json.loads((output / "experiment" / "metrics.json").read_text(encoding="utf-8"))
    assert ASSISTIVE_DISCLAIMER in json.dumps(metrics, ensure_ascii=False)
    assert list((output / "experiment" / "panels").glob("*.png"))
    with pytest.raises(FileExistsError):
        run_demo(output)
