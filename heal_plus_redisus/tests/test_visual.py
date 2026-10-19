"""Synthetic technical safety tests; these are not clinical validation evidence."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import cv2
import numpy as np
import pytest
from pydantic import ValidationError

from heal_plus_redisus.src.safety import ASSISTIVE_DISCLAIMER
from heal_plus_redisus.src.sprint2_clinical_visual.guided_capture_validator import (
    CaptureMeasurements,
    GuidedCaptureValidator,
)
from heal_plus_redisus.src.sprint2_clinical_visual.statistical_analyzer import StatisticalAnalyzer
from heal_plus_redisus.src.sprint2_clinical_visual.temporal_heatmap import (
    AlignmentEvidence,
    ScaleCalibration,
    TemporalFrame,
    TemporalHeatmap,
)
from heal_plus_redisus.src.sprint2_clinical_visual.visual_inspector import (
    FEATURE_CATALOG,
    ClinicalVisualInspector,
    EquityCounts,
    ObservationState,
    VisualInspection,
)

NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)


def annotation(image="image-1", category="D", **values):
    defaults = dict(
        image_id=image, dataset_id="public-approved-1", category=category, reviewer_id="professional-1", reviewed_at=NOW
    )
    defaults.update(values)
    return VisualInspection(**defaults)


@pytest.mark.parametrize("tia,review_required", [(0.249, False), (0.25, True), (1.0, True)])
def test_assistive_uncertainty_requests_review_at_25_percent(tia, review_required):
    report = ClinicalVisualInspector().inspect(annotation(tia=tia))
    assert any("Incerteza assistiva elevada" in prompt for prompt in report.review_prompts) is review_required


def test_orthogonal_E_rejection_is_included_without_relabeling_intermediate_case():
    row = annotation(category="INTERMEDIATE", tia=0.4, features={"F03": "presente"})
    normal = StatisticalAnalyzer().analyze([row])
    extended = StatisticalAnalyzer().analyze([row], failure_categories=("C", "D", "E"))
    assert normal.failure_count == 0
    assert extended.failure_count == 1
    assert row.category == "INTERMEDIATE"


def valid_capture(**overrides):
    values = dict(
        distance_cm=25,
        distance_source="medida_manual",
        angle_to_wound_plane_deg=90,
        angle_source="plano_medido_manualmente",
        scale_present=True,
        scale_next_to_wound=True,
        framing_complete=True,
        neutral_background=True,
        privacy_checked=True,
        consent_to_capture=True,
        identifying_exif_removed=True,
    )
    values.update(overrides)
    return CaptureMeasurements(**values)


def textured_image(dark=False):
    rng = np.random.default_rng(123)
    base = 55 if dark else 140
    intensity = rng.integers(base - 10, base + 11, size=(96, 96), dtype=np.uint8)
    return np.repeat(intensity[..., None], 3, axis=2)


def temporal_frames():
    labels = np.zeros((64, 64), dtype=np.uint8)
    roi = np.zeros_like(labels, dtype=bool)
    roi[12:52, 12:52] = True
    uncertain = np.zeros_like(roi)
    calibration = ScaleCalibration(10, 20, "mm", "professional-1", True)
    previous = TemporalFrame("subject-1", "wound-1", NOW, labels, roi, uncertain, calibration, "nenhuma_registrada")
    current = replace(previous, captured_at=NOW + timedelta(days=7), labels=labels.copy())
    points = np.array([[5, 5], [32, 5], [58, 5], [5, 58], [32, 58], [58, 58], [5, 32], [58, 32]], dtype=np.float64)
    evidence = AlignmentEvidence(points, points.copy(), "professional-1", True)
    return previous, current, evidence


def test_protocol_24_features_unknown_is_not_absent():
    report = ClinicalVisualInspector().inspect(annotation())
    assert len(FEATURE_CATALOG) >= 24
    assert report.feature_states["C01"] == ObservationState.UNKNOWN
    assert report.feature_states["C01"] != ObservationState.ABSENT
    assert report.disclaimer == ASSISTIVE_DISCLAIMER


def test_professional_review_and_etiology_requirements_do_not_stage():
    row = annotation(
        features={
            "C01": "presente",
            "C02": "presente",
            "C03": "presente",
            "C07": "presente",
            "C08": "presente",
            "E01": "presente",
        },
        etiology="arterial",
    )
    report = ClinicalVisualInspector().inspect(row)
    assert "wifi_i" in report.missing_clinical_fields
    assert "fontaine" in report.required_clinical_fields
    assert report.reviewed
    assert any("cor isolada" in prompt for prompt in report.review_prompts)
    assert any("profissional" in prompt for prompt in report.review_prompts)
    assert not hasattr(report, "diagnosis") and not hasattr(report, "stage")


def test_provisional_review_unknown_codes_and_naive_timestamp():
    row = VisualInspection(image_id="image", dataset_id="dataset", category="A")
    assert not ClinicalVisualInspector().inspect(row).reviewed
    with pytest.raises(ValidationError):
        annotation(features={"invented": "presente"})
    with pytest.raises(ValidationError):
        annotation(reviewed_at=datetime(2026, 10, 19))


def test_factor_statistics_known_denominators_and_zero_control():
    records = [
        annotation("a", "D", features={"C01": "presente"}, dice=0.4, tia=0.6),
        annotation("b", "D"),
        annotation("c", "A", features={"C01": "ausente"}, dice=0.9),
    ]
    report = StatisticalAnalyzer().analyze(records)
    feature = next(row for row in report.comparisons if row.code == "C01")
    assert feature.failure.present == 1 and feature.failure.observed == 1
    assert feature.failure.unknown == 1 and feature.failure.total == 2
    assert feature.failure.proportion == 1
    assert feature.prevalence_ratio is None
    assert feature.ratio_status == "indeterminado_denominador_zero"
    assert feature.dice_with_factor.mean == pytest.approx(0.4)
    assert feature.dice_without_factor.mean == pytest.approx(0.9)


def test_statistical_skin_stratification_and_explicit_false_positive_denominator():
    report = StatisticalAnalyzer().analyze(
        [
            annotation(
                "a",
                "D",
                features={"E01": "presente"},
                skin_tone="escuro_retinto",
                equity_counts=EquityCounts(necrosis_false_positive_pixels=5, non_necrosis_reference_pixels=100),
            ),
            annotation("b", "A", features={"E01": "presente"}, skin_tone="escuro_retinto"),
        ]
    )
    factor = next(row for row in report.comparisons if row.code == "E01")
    assert factor.prevalence_ratio == 1
    assert report.equity_by_skin_tone["escuro_retinto"].necrosis_false_positive_rate == 0.05
    assert report.equity_by_skin_tone["claro"].necrosis_false_positive_rate is None
    assert "public-approved-1" in report.by_dataset


def test_statistics_empty_unreviewed_duplicate_and_cde_group_selection():
    empty = StatisticalAnalyzer().analyze([])
    assert empty.control_count == 0
    assert all(row.prevalence_ratio is None for row in empty.comparisons)
    provisional = VisualInspection(image_id="x", dataset_id="dataset", category="D")
    assert StatisticalAnalyzer().analyze([provisional]).excluded_unreviewed == 1
    with pytest.raises(ValueError):
        StatisticalAnalyzer().analyze([annotation(), annotation()])
    assert (
        StatisticalAnalyzer().analyze([annotation(category="C")], failure_categories=("C", "D", "E")).failure_count == 1
    )


@pytest.mark.parametrize("dark", [False, True])
def test_capture_accepts_relative_illumination_for_light_and_dark_skin(dark):
    rgb = textured_image(dark)
    report = GuidedCaptureValidator().validate(rgb, valid_capture(), perilesional_mask=np.ones(rgb.shape[:2], bool))
    assert report.status == "aceito"
    assert report.disclaimer == ASSISTIVE_DISCLAIMER


def test_intermediate_sprint1_category_is_retained_without_forced_statistical_group():
    from heal_plus_redisus.src.sprint1_pipeline.cascade_evaluator import categorize_failure

    category, _ = categorize_failure(0.70, 0.60, 0.70, 20)
    assert category == "INTERMEDIATE"
    row = annotation(category=category)
    inspection = ClinicalVisualInspector().inspect(row)
    assert inspection.image_id == row.image_id
    result = StatisticalAnalyzer().analyze([row])
    assert result.failure_count == 0 and result.control_count == 0


def test_capture_missing_distance_angle_never_inferred_from_pixels():
    rgb = textured_image()
    measurements = valid_capture(
        distance_cm=None, distance_source=None, angle_to_wound_plane_deg=None, angle_source=None
    )
    report = GuidedCaptureValidator().validate(rgb, measurements, perilesional_mask=np.ones(rgb.shape[:2], bool))
    assert report.status == "indeterminado"
    assert next(check for check in report.checks if check.code == "F01").value is None
    assert next(check for check in report.checks if check.code == "F02").value is None
    with pytest.raises(ValidationError):
        CaptureMeasurements(distance_cm=25)
    with pytest.raises(ValidationError):
        CaptureMeasurements(angle_to_wound_plane_deg=90, angle_source="device_orientation")


@pytest.mark.parametrize(
    "field", ["consent_to_capture", "privacy_checked", "identifying_exif_removed", "scale_present"]
)
def test_capture_rejects_failed_privacy_consent_scale_checklist(field):
    rgb = textured_image()
    report = GuidedCaptureValidator().validate(
        rgb, valid_capture(**{field: False}), perilesional_mask=np.ones(rgb.shape[:2], bool)
    )
    assert report.status == "rejeitado"


def test_capture_rejects_blur_angle_and_distance():
    rgb = textured_image()
    blurred = cv2.GaussianBlur(rgb, (15, 15), 5)
    report = GuidedCaptureValidator().validate(
        blurred,
        valid_capture(distance_cm=60, angle_to_wound_plane_deg=50),
        perilesional_mask=np.ones(rgb.shape[:2], bool),
    )
    assert report.status == "rejeitado"
    assert {check.code for check in report.checks if check.status == "rejeitado"} >= {"F01", "F02", "F04"}


def test_capture_requires_perilesional_reference_and_valid_rgb():
    assert GuidedCaptureValidator().validate(textured_image(True), valid_capture()).status == "indeterminado"
    with pytest.raises(ValueError):
        GuidedCaptureValidator().validate(np.zeros((64, 64)), valid_capture())


def test_temporal_aligned_change_excludes_uncertainty_and_reports_mm2():
    previous, current, evidence = temporal_frames()
    current.labels[20:30, 20:30] = 1
    current.labels[30:40, 30:40] = 4
    result = TemporalHeatmap().compare(previous, current, evidence)
    assert result.status == "comparavel"
    assert result.changed_tissue_pixels == 100
    assert result.compared_pixels == 1500
    assert result.current.uncertain_pixels == 100
    assert result.previous.roi_area_mm2 == pytest.approx(400)
    assert result.area_change_mm2 == 0
    assert not result.comparison_mask[35, 35]
    assert np.all(result.heatmap_rgb[35, 35] == 0)
    assert result.disclaimer == ASSISTIVE_DISCLAIMER


def test_temporal_independent_mm_cm_calibrations_agree():
    previous, current, evidence = temporal_frames()
    current = replace(current, calibration=ScaleCalibration(1, 20, "cm", "professional", True))
    result = TemporalHeatmap().compare(previous, current, evidence)
    assert result.status == "comparavel" and result.area_change_mm2 == 0


def test_temporal_rejects_cross_patient_cross_wound_and_nonchronological_visits():
    previous, current, evidence = temporal_frames()
    for wrong in (
        replace(current, patient_id="subject-2"),
        replace(current, wound_id="wound-2"),
        replace(current, captured_at=NOW),
    ):
        with pytest.raises(ValueError):
            TemporalHeatmap().compare(previous, wrong, evidence)


def test_temporal_missing_scale_or_landmarks_is_indeterminate():
    previous, current, evidence = temporal_frames()
    assert TemporalHeatmap().compare(previous, replace(current, calibration=None), evidence).status == "indeterminado"
    assert TemporalHeatmap().compare(previous, current, None).status == "indeterminado"
    assert (
        TemporalHeatmap().compare(previous, current, replace(evidence, approximately_planar=False)).status
        == "indeterminado"
    )


def test_temporal_degenerate_landmarks_and_incompatible_scale_do_not_make_heatmap():
    previous, current, evidence = temporal_frames()
    line = np.array([[index, index] for index in range(8)], dtype=float)
    result = TemporalHeatmap().compare(
        previous, current, replace(evidence, current_points=line, previous_points=line.copy())
    )
    assert result.status == "indeterminado" and result.heatmap_rgb is None
    wrong_scale = ScaleCalibration(50, 20, "mm", "professional", True)
    assert (
        TemporalHeatmap().compare(previous, replace(current, calibration=wrong_scale), evidence).status
        == "indeterminado"
    )


def test_temporal_all_uncertain_and_post_debridement_context():
    previous, current, evidence = temporal_frames()
    current = replace(current, labels=np.full_like(current.labels, 4), intervention="pos_desbridamento")
    result = TemporalHeatmap().compare(previous, current, evidence)
    assert result.status == "indeterminado" and result.heatmap_rgb is None
    assert any("pós-desbridamento" in note for note in result.contextual_notes)


def test_temporal_ransac_handles_outlier_correspondences():
    previous, current, evidence = temporal_frames()
    altered = evidence.previous_points.copy()
    altered[0] = [17, 18]
    altered[2] = [45, 19]
    result = TemporalHeatmap().compare(previous, current, replace(evidence, previous_points=altered))
    assert result.status == "comparavel"
    assert result.inlier_fraction == pytest.approx(0.75)
    assert result.median_reprojection_error_px < 1e-4


def test_equity_counts_invalid_or_missing_denominator_are_rejected():
    with pytest.raises(ValidationError):
        EquityCounts(necrosis_false_positive_pixels=5)
    with pytest.raises(ValidationError):
        EquityCounts(necrosis_false_positive_pixels=5, non_necrosis_reference_pixels=4)
