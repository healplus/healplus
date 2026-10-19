"""Synthetic engineering tests; no clinical/dataset effectiveness is asserted."""

from __future__ import annotations

import hashlib
import json

import numpy as np
from PIL import Image
import pytest

from heal_plus_redisus.src.safety import ASSISTIVE_DISCLAIMER
from heal_plus_redisus.src.sprint1_pipeline import HybridSegmenter, ROI, ROIHandler, TISSUE_CLASSES, triad_zones
from heal_plus_redisus.src.sprint1_pipeline.cascade_evaluator import (
    CascadeEvaluator,
    DetectionSample,
    YoloDetectorAdapter,
    bbox_iou,
    categorize_failure,
    detection_map,
    mask_metrics,
    match_rois,
)
from heal_plus_redisus.src.sprint1_pipeline.hybrid_segmenter import (
    FEATURE_NAMES,
    NeuralPrediction,
    extract_features,
    merge_results,
)
from heal_plus_redisus.src.sprint1_pipeline.report_sprint1 import export_experiment


@pytest.fixture
def image():
    return np.random.default_rng(71).integers(40, 210, (64, 80, 3), dtype=np.uint8)


class _Backend:
    validated = True
    model_version = "synthetic-contract-fixture"
    feature_names = FEATURE_NAMES

    def __init__(self, tissue_class=0, diffuse=False):
        self.tissue_class, self.diffuse = tissue_class, diffuse

    def predict(self, features):
        assert features.shape[-1] == 27
        probabilities = np.full((*features.shape[:2], 5), 0.2 if self.diffuse else 0.0025, np.float32)
        if not self.diffuse:
            probabilities[..., self.tissue_class] = 0.99
        return NeuralPrediction(probabilities, np.full(features.shape[:2], 0.99, np.float32))


class _Detector:
    def __init__(self, rois):
        self.rois = rois

    def detect(self, image_rgb):
        return self.rois


def test_roi_context_multiple_and_bounds(image):
    roi = ROI("wound-1", (20, 20, 40, 40))
    assert roi.expanded_bbox(image.shape) == (15, 15, 45, 45)
    assert ROI("edge", (0, 0, 8, 8)).expanded_bbox(image.shape) == (0, 0, 10, 10)
    assert ROIHandler().crop(image, roi)[0].shape == (30, 30, 3)
    with pytest.raises(ValueError, match="unique"):
        ROIHandler().validate(image, [roi, roi])
    with pytest.raises(ValueError, match="beyond"):
        ROI("outside", (0, 0, 1000, 50)).mask(image.shape)


@pytest.mark.parametrize("bbox", [(4, 4, 4, 5), (-1, 0, 5, 5), (0, 0, 3.0, 4)])
def test_invalid_roi(bbox):
    with pytest.raises(ValueError):
        ROI("wound", bbox)


def test_image_budget_rejects_large_broadcast_view_without_allocating_pixels():
    from heal_plus_redisus.src.sprint1_pipeline.roi_handler import validate_rgb

    image_view = np.broadcast_to(np.zeros((1, 1, 3), np.uint8), (4000, 4000, 3))
    with pytest.raises(ValueError, match="12 megapixels.*manifesto"):
        validate_rgb(image_view)


def test_roi_map_budget_is_aggregate_and_guides_manifest_recording(image, monkeypatch):
    import heal_plus_redisus.src.sprint1_pipeline.roi_handler as roi_module

    monkeypatch.setattr(roi_module, "MAX_RESULT_PIXELS", image.shape[0] * image.shape[1] + 1)
    rois = [ROI("one", (10, 10, 20, 20)), ROI("two", (30, 30, 40, 40))]
    with pytest.raises(ValueError, match="agregado.*preservando a escala.*manifesto"):
        ROIHandler().validate(image, rois)


def test_context_budget_applies_before_features_even_for_direct_segment(image, monkeypatch):
    import heal_plus_redisus.src.sprint1_pipeline.roi_handler as roi_module
    import heal_plus_redisus.src.sprint1_pipeline.hybrid_segmenter as segmenter_module

    monkeypatch.setattr(roi_module, "MAX_CONTEXT_PIXELS", 100)

    def forbidden_features(*args, **kwargs):
        raise AssertionError("Features must not be allocated before the crop budget is validated")

    monkeypatch.setattr(segmenter_module, "extract_features", forbidden_features)
    with pytest.raises(ValueError, match="contextual.*manifesto"):
        HybridSegmenter().segment(image, ROI("one", (10, 10, 30, 30)), context={"etiology": "unknown"})


def test_detector_provenance_is_paired_and_upstream_metadata_only():
    with pytest.raises(ValueError, match="together"):
        YoloDetectorAdapter(object(), model_version="v1")
    with pytest.raises(ValueError, match="hexadecimal"):
        YoloDetectorAdapter(object(), checkpoint_sha256="bad", model_version="v1")
    adapter = YoloDetectorAdapter(object(), checkpoint_sha256="A" * 64, model_version="reviewed-v1")
    assert adapter.checkpoint_sha256 == "a" * 64
    assert adapter.model_version == "reviewed-v1"
    assert YoloDetectorAdapter(object()).checkpoint_sha256 is None


def test_triad_exclusive_and_not_a_clinical_boundary():
    mask = np.zeros((48, 48), bool)
    mask[15:32, 15:32] = True
    zones = triad_zones(mask)
    assert zones.bed.any() and zones.border.any() and zones.perilesional.any()
    assert not np.any(zones.bed & zones.border)
    assert not np.any(zones.border & zones.perilesional)
    assert "proxy" in zones.provenance
    assert not triad_zones(np.zeros_like(mask)).border.any()


def test_no_checkpoint_abstains_and_does_not_invent_bed(image):
    roi = ROI("wound", (10, 12, 50, 48))
    result = HybridSegmenter().segment(image, roi, context={"etiology": "unknown"})
    assert not result.bed_mask.any()
    assert result.status == "abstained_no_validated_model"
    assert result.percentages_scope == "unlocalized_roi"
    assert np.all(result.class_map[roi.mask(image.shape)] == 4)
    assert np.all(result.class_map[~roi.mask(image.shape)] == 255)
    assert result.tissue_percentages[TISSUE_CLASSES[4]] == 100
    assert result.tia_percent == 100
    assert result.to_dict()["disclaimer"] == ASSISTIVE_DISCLAIMER


def test_unapproved_backend_is_never_run(image):
    class Forbidden(_Backend):
        validated = False

        def predict(self, features):
            raise AssertionError("Unvalidated model was used")

    result = HybridSegmenter(Forbidden()).segment(image, ROI("w", (10, 10, 30, 30)), context={"etiology": "venous"})
    assert result.bed_source == "unavailable"


def test_professional_bed_separate_from_uncertain_tissue(image):
    roi = ROI("w", (10, 10, 50, 50))
    bed = np.zeros(image.shape[:2], bool)
    bed[20:40, 20:40] = True
    result = HybridSegmenter().segment(image, roi, context={"etiology": "pressure"}, bed_mask=bed)
    assert np.array_equal(result.bed_mask, bed)
    assert np.all(result.class_map[bed] == 4)
    assert np.all(result.class_map[~bed] == 255)
    assert result.bed_uncertainty_percent == 100
    assert result.tia_percent == 25


@pytest.mark.parametrize("context", [{}, {"etiology": "diagnosis"}, {"etiology": "unknown", "suspected_blood": "yes"}])
def test_explicit_clinical_context_required(image, context):
    with pytest.raises(ValueError):
        HybridSegmenter().segment(image, ROI("w", (10, 10, 30, 30)), context=context)


@pytest.mark.parametrize("tissue_class", range(5))
def test_five_classes_are_neural_outputs_and_percentages_sum_to_100(image, tissue_class):
    roi = ROI("w", (15, 15, 40, 40))
    result = HybridSegmenter(_Backend(tissue_class)).segment(image, roi, context={"etiology": "unknown"})
    assert tuple(result.tissue_percentages) == TISSUE_CLASSES
    assert sum(result.tissue_percentages.values()) == pytest.approx(100)
    assert result.tissue_percentages[TISSUE_CLASSES[tissue_class]] > 90
    assert np.all(result.class_map[~roi.mask(image.shape)] == 255)
    if tissue_class == 4:
        assert np.min(result.uncertainty[result.bed_mask]) >= 0.65


def test_entropy_and_artifacts_cause_abstention(image):
    roi = ROI("w", (15, 15, 40, 40))
    uncertain = HybridSegmenter(_Backend(diffuse=True)).segment(image, roi, context={"etiology": "other"})
    assert uncertain.bed_uncertainty_percent == 100
    blood = np.zeros(image.shape[:2], bool)
    blood[20:30, 20:30] = True
    result = HybridSegmenter(_Backend()).segment(
        image, roi, context={"etiology": "other"}, artifact_masks={"blood": blood}
    )
    assert np.all(result.class_map[blood] == 4)
    assert np.all(result.uncertainty[blood] == 1)
    dressing = HybridSegmenter(_Backend()).segment(image, roi, context={"etiology": "other", "residual_dressing": True})
    assert dressing.bed_uncertainty_percent == 100


def test_dark_skin_is_not_a_necrosis_rule_or_absolute_luminance_rejection():
    yy, xx = np.indices((64, 64))
    gray = np.where((xx + yy) % 2, 18, 35).astype(np.uint8)
    dark = np.repeat(gray[..., None], 3, axis=-1)
    bed = np.zeros((64, 64), bool)
    bed[20:44, 20:44] = True
    features, summary, artifacts = extract_features(dark, bed, {"etiology": "unknown"})
    assert summary["perilesional_reference_available"]
    assert artifacts.mean() < 0.1
    assert len(FEATURE_NAMES) == features.shape[-1]
    result = HybridSegmenter(_Backend()).segment(dark, ROI("w", (15, 15, 50, 50)), context={"etiology": "unknown"})
    assert result.tissue_percentages["necrose"] == 0
    assert result.tissue_percentages["granulacao"] > 90


def test_invalid_neural_output_rejected(image):
    class Invalid(_Backend):
        def predict(self, features):
            result = super().predict(features)
            result.probabilities[0, 0, 0] = np.nan
            return result

    with pytest.raises(ValueError, match="invalid probabilities"):
        HybridSegmenter(Invalid()).segment(image, ROI("w", (10, 10, 30, 30)), context={"etiology": "unknown"})


def test_overlapping_proposals_never_hide_uncertainty_or_disagreement(image):
    roi = ROI("w", (15, 15, 40, 40))
    first = HybridSegmenter(_Backend(0)).segment(image, roi, context={"etiology": "other"})
    contradictory = HybridSegmenter(_Backend(2)).segment(image, roi, context={"etiology": "other"})
    bed, labels, uncertainty = merge_results([first, contradictory], image.shape[:2])
    assert np.all(labels[bed] == 4)
    assert np.min(uncertainty[bed]) >= 0.65
    second = HybridSegmenter(_Backend(0)).segment(image, roi, context={"etiology": "other"})
    second.artifact_mask[20:30, 20:30] = True
    _, labels, uncertainty = merge_results([first, second], image.shape[:2])
    assert np.all(labels[20:30, 20:30] == 4)
    assert np.all(uncertainty[20:30, 20:30] == 1)


def test_box_matching_penalizes_missing_extra_and_duplicate_detections():
    first, second = ROI("a", (0, 0, 10, 10)), ROI("b", (30, 30, 40, 40))
    assert bbox_iou(first, first) == 1
    match = match_rois([first, second], [first])
    assert match.penalized_mean_iou == 0.5 and match.missed_reference == (1,)
    duplicated = match_rois([first], [first, ROI("dup", first.bbox)])
    assert duplicated.penalized_mean_iou == 0.5 and len(duplicated.extra_predictions) == 1


def test_detection_map_confidence_ordering_and_empty_truth():
    truth = ROI("truth", (0, 0, 10, 10))
    good = ROI("good", truth.bbox, 0.9, "detector")
    wrong = ROI("wrong", (30, 30, 40, 40), 0.99, "detector")
    perfect = detection_map([DetectionSample("a", (truth,), (good,))])
    assert perfect["map_50_95"] == pytest.approx(1)
    imperfect = detection_map([DetectionSample("a", (truth,), (wrong, good))])
    assert imperfect["ap50"] == pytest.approx(0.5)
    assert detection_map([DetectionSample("empty", (), ())])["map_50_95"] is None
    assert detection_map([DetectionSample("a", (truth,), ())])["map_50_95"] == 0


def test_mask_metrics_empty_and_error_conventions():
    empty = np.zeros((8, 8), bool)
    assert mask_metrics(empty, empty)["dice"] == 1
    assert mask_metrics(empty, empty)["sensitivity"] is None
    full = ~empty
    metrics = mask_metrics(empty, full)
    assert metrics["dice"] == 0 and metrics["sensitivity"] == 0 and metrics["specificity"] is None
    with pytest.raises(ValueError):
        mask_metrics(empty.astype(np.uint8), empty)


@pytest.mark.parametrize(
    "scores,expected",
    [
        ((0.9, 0.9, 0.9, 5), ("A", False)),
        ((0.9, 0.4, 0.4, 10), ("B", False)),
        ((0.3, 0.8, 0.3, 10), ("C", False)),
        ((0.3, 0.3, 0.3, 40), ("D", True)),
        ((0.7, 0.6, 0.7, 30), ("INTERMEDIATE", False)),
    ],
)
def test_technical_categories_and_orthogonal_safe_rejection(scores, expected):
    assert categorize_failure(*scores) == expected


def test_reference_bed_is_never_fed_into_experiment_by_accident(image):
    roi = ROI("w", (15, 15, 40, 40))
    truth = roi.mask(image.shape)
    evaluation = CascadeEvaluator(HybridSegmenter(), _Detector([])).evaluate(
        "img-1",
        image,
        [roi],
        {roi.id: truth},
        context={"etiology": "unknown"},
    )
    assert not evaluation.manual_results[0].bed_mask.any()
    assert evaluation.record.dice_manual == 0
    assert evaluation.record.categories == ("D", "E")
    assert evaluation.record.missed_lesions == 1


def test_multilesion_cascade_penalizes_one_missed_lesion_without_losing_E(image):
    rois = [ROI("one", (10, 10, 25, 25)), ROI("two", (45, 35, 60, 50))]
    truth = {roi.id: roi.mask(image.shape) for roi in rois}
    evaluation = CascadeEvaluator(HybridSegmenter(_Backend()), _Detector([rois[0]])).evaluate(
        "multi-1",
        image,
        rois,
        truth,
        context={"etiology": "other"},
    )
    assert evaluation.record.dice_manual == pytest.approx(1)
    assert evaluation.record.detector_iou == 0.5
    assert evaluation.record.dice_cascade == pytest.approx(2 / 3)
    assert evaluation.record.missed_lesions == 1
    assert evaluation.record.tia_percent >= 50
    assert evaluation.record.categories == ("B", "E")


def test_report_metrics_panels_and_complete_disclaimer(image, tmp_path):
    roi = ROI("w", (15, 15, 40, 40))
    evaluation = CascadeEvaluator(HybridSegmenter(), _Detector([])).evaluate(
        "img-1",
        image,
        [roi],
        {roi.id: roi.mask(image.shape)},
        context={"etiology": "unknown"},
    )
    paths = export_experiment([evaluation], {"img-1": image}, tmp_path)
    assert json.loads(paths["json"].read_text(encoding="utf-8"))["records"][0]["categories"] == ["D", "E"]
    aggregate = json.loads(paths["aggregate"].read_text(encoding="utf-8"))
    assert aggregate["detection"]["map_50_95"] == 0
    assert aggregate["uncertainty_rejection_count"] == 1
    assert len(paths["panels"]) == 1
    panel = Image.open(paths["panels"][0])
    assert panel.info["Description"] == ASSISTIVE_DISCLAIMER
    assert panel.width == 3500 and panel.height == 1190


def test_torch_unet_training_shapes_and_checkpoint_integrity(tmp_path):
    torch = pytest.importorskip("torch")
    from heal_plus_redisus.src.sprint1_pipeline.neural import (
        CheckpointApproval,
        TissueProposalUNet,
        TorchUNetBackend,
        joint_loss,
    )

    torch.set_num_threads(1)
    model = TissueProposalUNet(base_channels=4)
    output = model(torch.zeros(1, len(FEATURE_NAMES), 19, 23))
    assert output["tissue_logits"].shape == (1, 5, 19, 23)
    assert output["bed_logits"].shape == (1, 1, 19, 23)
    loss = joint_loss(output, torch.full((1, 19, 23), 255), torch.zeros(1, 19, 23))
    assert torch.isfinite(loss)
    loss.backward()
    approval = CheckpointApproval("test-v1", "0" * 64, "review-fixture", True)
    assert not TorchUNetBackend(model, approval=approval, checkpoint_sha256="0" * 64).validated
    checkpoint = tmp_path / "model.pt"
    torch.save(
        {"state_dict": model.state_dict(), "feature_names": list(FEATURE_NAMES), "model_version": "test-v1"}, checkpoint
    )
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="integrity"):
        TorchUNetBackend.from_checkpoint(checkpoint, expected_sha256="0" * 64, approval=approval, base_channels=4)
    backend = TorchUNetBackend.from_checkpoint(
        checkpoint, expected_sha256=digest, approval=approval, base_channels=4, max_side=32
    )
    # Synthetic checkpoint exercises the transport only; never a clinical assertion.
    prediction = backend.predict(np.zeros((17, 29, len(FEATURE_NAMES)), np.float32))
    assert prediction.probabilities.shape == (17, 29, 5)
    assert prediction.bed_probability.shape == (17, 29)
    assert np.allclose(prediction.probabilities.sum(-1), 1)
