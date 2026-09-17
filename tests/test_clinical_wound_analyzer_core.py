import cv2
import numpy as np
import pytest
from types import SimpleNamespace

from src.processing.clinical_wound_analyzer_core import ClinicalReport, ClinicalWoundAnalyzer


def test_headless_core_imports_and_analyzes_without_pyqt(red_wound_frame):
    analyzer = ClinicalWoundAnalyzer()

    report = analyzer.analyze(red_wound_frame)

    assert isinstance(report, ClinicalReport)
    assert isinstance(report.is_valid_wound, bool)
    assert isinstance(report.primary_tissue, str)
    assert 0 <= report.health_score <= 100
    assert report.processing_time_ms >= 0
    assert isinstance(report.tissue_analysis_trace, (dict, type(None)))
    if not report.is_valid_wound:
        assert report.rejection_reason


def test_headless_core_rejects_empty_frame():
    analyzer = ClinicalWoundAnalyzer()

    report = analyzer.analyze(np.zeros((0, 0, 3), dtype=np.uint8))

    assert isinstance(report, ClinicalReport)
    assert report.is_valid_wound is False
    assert report.rejection_reason


def test_segment_clinical_v3_detects_mixed_dark_yellow_red_tissues():
    analyzer = ClinicalWoundAnalyzer()

    image = np.full((320, 320, 3), (180, 200, 220), dtype=np.uint8)
    wound_mask = np.zeros((320, 320), dtype=np.uint8)
    cv2.circle(wound_mask, (160, 160), 100, 255, -1)

    cv2.circle(image, (160, 160), 100, (40, 60, 180), -1)
    cv2.ellipse(image, (190, 145), (45, 28), 10, 0, 360, (120, 200, 210), -1)
    cv2.ellipse(image, (135, 175), (38, 30), -20, 0, 360, (25, 55, 65), -1)

    peripheral_zone, core_zone, outer_ring = analyzer._create_zone_masks(wound_mask)
    tissue_pcts, segmentation_map, overlay = analyzer._segment_clinical_v3(
        image,
        wound_mask,
        peripheral_zone,
        core_zone,
        outer_ring,
    )

    assert tissue_pcts["slough"] > 20.0
    assert tissue_pcts["necrosis"] > 20.0
    assert tissue_pcts["slough"] > tissue_pcts["granulation"]
    assert np.all(segmentation_map[wound_mask == 0] == 0)
    assert np.all(segmentation_map[wound_mask > 0].sum(axis=1) > 0)
    contour_margin = cv2.dilate(wound_mask, np.ones((7, 7), dtype=np.uint8))
    assert np.array_equal(overlay[contour_margin == 0], image[contour_margin == 0])


def test_segment_clinical_v3_detects_olive_slough_pressure_injury_pattern():
    analyzer = ClinicalWoundAnalyzer()

    image = np.full((360, 360, 3), (180, 200, 220), dtype=np.uint8)
    wound_mask = np.zeros((360, 360), dtype=np.uint8)
    cv2.circle(wound_mask, (180, 180), 105, 255, -1)

    cv2.circle(image, (180, 180), 105, (100, 130, 125), -1)
    cv2.ellipse(image, (180, 120), (48, 30), 0, 0, 360, (70, 75, 190), -1)
    cv2.ellipse(image, (185, 255), (55, 32), 0, 0, 360, (70, 75, 185), -1)
    cv2.circle(image, (152, 188), 13, (25, 30, 40), -1)
    cv2.circle(image, (220, 232), 15, (30, 35, 45), -1)

    peripheral_zone, core_zone, outer_ring = analyzer._create_zone_masks(wound_mask)
    tissue_pcts, _, _ = analyzer._segment_clinical_v3(
        image,
        wound_mask,
        peripheral_zone,
        core_zone,
        outer_ring,
    )

    assert tissue_pcts["slough"] > 30.0
    assert tissue_pcts["slough"] > tissue_pcts["granulation"]
    assert tissue_pcts["necrosis"] > 2.0


def test_analyze_fragments_roi_and_still_recovers_pressure_injury_like_slough():
    analyzer = ClinicalWoundAnalyzer()

    image = np.full((420, 420, 3), (175, 188, 205), dtype=np.uint8)
    cv2.circle(image, (210, 210), 120, (100, 130, 125), -1)
    cv2.ellipse(image, (210, 110), (55, 40), 0, 0, 360, (70, 75, 190), -1)
    cv2.ellipse(image, (210, 305), (60, 42), 0, 0, 360, (70, 75, 185), -1)
    cv2.circle(image, (165, 135), 10, (25, 30, 40), -1)
    cv2.circle(image, (255, 295), 12, (22, 28, 38), -1)
    cv2.circle(image, (190, 210), 14, (45, 60, 70), -1)

    fragmented_detections = [
        SimpleNamespace(bbox=(130, 60, 290, 165), confidence=0.92),
        SimpleNamespace(bbox=(125, 255, 300, 355), confidence=0.88),
    ]

    analyzer.detector.detect = lambda _image: fragmented_detections

    report = analyzer.analyze(image)

    assert report.is_valid_wound is True
    assert any("Esfacelo" in tissue.name for tissue in report.tissues)
    tissue_map = {t.name_en: t.percentage for t in report.tissues}
    assert tissue_map["Slough (Fibrin)"] > tissue_map["Granulation Tissue"]
    assert tissue_map["Coagulation Necrosis (Eschar)"] > 2.0


def test_analyze_uses_manual_roi_as_primary_filter():
    analyzer = ClinicalWoundAnalyzer()
    analyzer._validate_wound_image = lambda _image: True
    analyzer._predict_dl = lambda _image: None
    analyzer._predict_resnet = lambda _image: None
    analyzer._predict_ensemble = lambda _image, _detections, dl_probs=None, wound_mask=None: None

    image = np.full((240, 240, 3), (180, 200, 220), dtype=np.uint8)
    cv2.circle(image, (80, 120), 46, (50, 60, 190), -1)
    cv2.circle(image, (170, 120), 44, (120, 200, 210), -1)

    analyzer.detector.detect = lambda _image: [SimpleNamespace(bbox=(20, 40, 220, 200), confidence=0.95)]

    manual_mask = np.zeros((240, 240), dtype=np.uint8)
    cv2.circle(manual_mask, (80, 120), 50, 255, -1)

    report = analyzer.analyze(
        image,
        manual_roi_mask=manual_mask,
        roi_metadata={
            "tool": "polygon",
            "confirmed": True,
            "points": [
                {"x": 0.12, "y": 0.28},
                {"x": 0.42, "y": 0.28},
                {"x": 0.42, "y": 0.72},
                {"x": 0.12, "y": 0.72},
            ],
        },
    )

    assert report.is_valid_wound is True
    assert report.roi["source"] == "manual"
    assert report.roi["tool"] == "polygon"
    assert report.wound_area_px == int(np.sum(manual_mask > 0))
    assert report.roi["area_px"] == report.wound_area_px


def test_analyze_supports_multiple_manual_rois():
    analyzer = ClinicalWoundAnalyzer()
    analyzer._validate_wound_image = lambda _image: True
    analyzer._predict_dl = lambda _image: None
    analyzer._predict_resnet = lambda _image: None
    analyzer._predict_ensemble = lambda _image, _detections, dl_probs=None, wound_mask=None: None

    image = np.full((260, 260, 3), (180, 200, 220), dtype=np.uint8)
    cv2.circle(image, (82, 130), 42, (50, 60, 190), -1)
    cv2.circle(image, (182, 128), 38, (120, 200, 210), -1)

    left_mask = np.zeros((260, 260), dtype=np.uint8)
    right_mask = np.zeros((260, 260), dtype=np.uint8)
    cv2.circle(left_mask, (82, 130), 48, 255, -1)
    cv2.circle(right_mask, (182, 128), 44, 255, -1)

    report = analyzer.analyze(
        image,
        manual_roi_masks=[left_mask, right_mask],
        roi_metadata={"selection_count": 2},
        roi_metadata_list=[
            {
                "tool": "polygon",
                "confirmed": True,
                "points": [
                    {"x": 0.1, "y": 0.32},
                    {"x": 0.36, "y": 0.32},
                    {"x": 0.36, "y": 0.72},
                    {"x": 0.1, "y": 0.72},
                ],
            },
            {
                "tool": "polygon",
                "confirmed": True,
                "points": [
                    {"x": 0.54, "y": 0.3},
                    {"x": 0.86, "y": 0.3},
                    {"x": 0.86, "y": 0.7},
                    {"x": 0.54, "y": 0.7},
                ],
            },
        ],
    )

    combined_area = int(np.sum(cv2.bitwise_or(left_mask, right_mask) > 0))

    assert report.is_valid_wound is True
    assert report.roi["source"] == "manual"
    assert report.roi["selection_count"] == 2
    assert report.rois is not None
    assert len(report.rois) == 2
    assert report.rois[0]["tool"] == "polygon"
    assert report.rois[1]["tool"] == "polygon"
    assert abs(report.wound_area_px - combined_area) < 250


def test_headless_core_rejects_nan_and_inf_inputs():
    analyzer = ClinicalWoundAnalyzer()

    # Image with NaNs
    nan_image = np.full((128, 128, 3), np.nan, dtype=np.float32)
    report_nan = analyzer.analyze(nan_image)
    assert isinstance(report_nan, ClinicalReport)
    assert report_nan.is_valid_wound is False
    assert "NaN/Inf" in report_nan.rejection_reason

    # Image with Infs
    inf_image = np.full((128, 128, 3), 100.0, dtype=np.float32)
    inf_image[64, 64, :] = np.inf
    report_inf = analyzer.analyze(inf_image)
    assert isinstance(report_inf, ClinicalReport)
    assert report_inf.is_valid_wound is False
    assert "NaN/Inf" in report_inf.rejection_reason


def test_headless_core_rejects_invalid_channel_counts():
    analyzer = ClinicalWoundAnalyzer()

    # 2-channel image
    two_channel = np.ones((64, 64, 2), dtype=np.uint8) * 128
    report_2ch = analyzer.analyze(two_channel)
    assert report_2ch.is_valid_wound is False
    assert "3 canais" in report_2ch.rejection_reason

    # 5-channel image
    five_channel = np.ones((64, 64, 5), dtype=np.uint8) * 128
    report_5ch = analyzer.analyze(five_channel)
    assert report_5ch.is_valid_wound is False
    assert "3 canais" in report_5ch.rejection_reason


@pytest.fixture
def synthetic_clinical_wound():
    image = np.full((320, 320, 3), (180, 200, 220), dtype=np.uint8)
    cv2.circle(image, (160, 160), 100, (40, 60, 180), -1)
    cv2.ellipse(image, (190, 145), (45, 28), 10, 0, 360, (120, 200, 210), -1)
    cv2.ellipse(image, (135, 175), (38, 30), -20, 0, 360, (25, 55, 65), -1)
    return image


def test_headless_core_accepts_and_converts_rgba_input(synthetic_clinical_wound):
    analyzer = ClinicalWoundAnalyzer()

    # Add alpha channel
    h, w, _ = synthetic_clinical_wound.shape
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    rgba_frame = np.concatenate([synthetic_clinical_wound, alpha], axis=-1)
    assert rgba_frame.shape == (h, w, 4)

    report = analyzer.analyze(rgba_frame)
    assert isinstance(report, ClinicalReport)
    assert report.is_valid_wound is True
    assert report.wound_area_px > 0


def test_headless_core_handles_float_inputs(synthetic_clinical_wound):
    analyzer = ClinicalWoundAnalyzer()

    # Float in [0.0, 1.0]
    float_01 = synthetic_clinical_wound.astype(np.float32) / 255.0
    report_01 = analyzer.analyze(float_01)
    assert report_01.is_valid_wound is True
    assert report_01.wound_area_px > 0

    # Float in [0.0, 255.0]
    float_255 = synthetic_clinical_wound.astype(np.float32)
    report_255 = analyzer.analyze(float_255)
    assert report_255.is_valid_wound is True
    assert report_255.wound_area_px > 0


def test_headless_core_rejects_subminimal_resolution():
    analyzer = ClinicalWoundAnalyzer()

    tiny = np.zeros((8, 8, 3), dtype=np.uint8)
    report = analyzer.analyze(tiny)
    assert report.is_valid_wound is False
    assert "resolução insuficiente" in report.rejection_reason


def test_headless_core_rejects_monochrome_solid_images():
    analyzer = ClinicalWoundAnalyzer()

    # Pure black
    black = np.zeros((100, 100, 3), dtype=np.uint8)
    assert analyzer.analyze(black).is_valid_wound is False

    # Pure white
    white = np.full((100, 100, 3), 255, dtype=np.uint8)
    assert analyzer.analyze(white).is_valid_wound is False

    # Pure gray
    gray = np.full((100, 100, 3), 128, dtype=np.uint8)
    assert analyzer.analyze(gray).is_valid_wound is False


def test_headless_core_rejects_high_frequency_synthetic_text():
    analyzer = ClinicalWoundAnalyzer()

    # Synthetic checkerboard/text pattern with dense edges
    dense_pattern = np.zeros((200, 200, 3), dtype=np.uint8)
    for i in range(0, 200, 4):
        dense_pattern[i, :] = 255
        dense_pattern[:, i] = 255

    report = analyzer.analyze(dense_pattern)
    assert report.is_valid_wound is False
    assert report.rejection_reason


def test_contract_stability_full_report_structure(synthetic_clinical_wound):
    analyzer = ClinicalWoundAnalyzer()
    report = analyzer.analyze(synthetic_clinical_wound)

    # Core contract checks
    assert isinstance(report.is_valid_wound, bool)
    assert isinstance(report.rejection_reason, str)
    assert isinstance(report.primary_tissue, str)
    assert isinstance(report.primary_justification, str)
    assert isinstance(report.wound_area_px, int)
    assert report.wound_area_px > 0
    assert 0.0 <= report.health_score <= 100.0
    assert report.processing_time_ms >= 0.0

    # Tissue taxonomy invariants
    assert len(report.tissues) == 4
    expected_tissue_names = {
        "Necrose de Coagulação (Escara)",
        "Esfacelo (Fibrina)",
        "Tecido de Granulação",
        "Epitelização",
    }
    found_names = {t.name for t in report.tissues}
    assert found_names == expected_tissue_names

    for tissue in report.tissues:
        assert isinstance(tissue.name, str)
        assert isinstance(tissue.name_en, str)
        assert 0.0 <= tissue.percentage <= 100.0
        assert len(tissue.color_bgr) == 3
        assert tissue.color_hex.startswith("#")
        assert len(tissue.description) > 0
        assert len(tissue.clinical_action) > 0

    # Spatial zones and ROI invariants
    assert report.wound_zones is not None
    assert "peripheral_area_px" in report.wound_zones
    assert "core_area_px" in report.wound_zones
    assert "outer_ring_area_px" in report.wound_zones
    assert report.roi is not None
    assert report.roi["source"] in ("automatic", "manual")


def test_degraded_mode_when_dl_segmenter_raises(synthetic_clinical_wound):
    analyzer = ClinicalWoundAnalyzer()

    # Simulate deep learning segmenter failure
    class FailingSegmenter:
        def predict(self, _image, **_kwargs):
            raise RuntimeError("Simulated segmentation DL CUDA out of memory")

    analyzer._wound_segmenter = FailingSegmenter()

    report = analyzer.analyze(synthetic_clinical_wound)
    assert report.is_valid_wound is True
    assert report.wound_segmentation is not None
    assert report.wound_segmentation["accepted"] is False
    assert report.wound_segmentation["fallback_reason"] == "runtime_error"
    assert "CUDA out of memory" in report.wound_segmentation["runtime_error"]
    assert report.wound_segmentation["final_mask_source"] == "classical_cv"


def test_degraded_mode_when_resnet_classifier_raises(synthetic_clinical_wound):
    analyzer = ClinicalWoundAnalyzer()

    # Simulate ResNet failure
    def failing_predict_resnet(_image):
        raise RuntimeError("Simulated ResNet tensor device error")

    analyzer._predict_resnet = failing_predict_resnet

    report = analyzer.analyze(synthetic_clinical_wound)
    assert report.is_valid_wound is True
    assert report.resnet_prediction is None


def test_degraded_mode_when_ensemble_raises(synthetic_clinical_wound):
    analyzer = ClinicalWoundAnalyzer()

    # Simulate Ensemble failure
    def failing_ensemble(*_args, **_kwargs):
        raise RuntimeError("Simulated ensemble orchestrator network timeout")

    analyzer._predict_ensemble = failing_ensemble

    report = analyzer.analyze(synthetic_clinical_wound)
    assert report.is_valid_wound is True
    assert report.ensemble_classification is None


def test_degraded_mode_when_enhancer_or_body_detector_raises(synthetic_clinical_wound):
    analyzer = ClinicalWoundAnalyzer()

    class FailingEnhancer:
        def analyze_lighting(self, _image):
            raise RuntimeError("Simulated enhancer crash")

    class FailingBodyDetector:
        def detect(self, _image):
            raise RuntimeError("Simulated body detector crash")

    analyzer.image_enhancer = FailingEnhancer()
    analyzer.body_detector = FailingBodyDetector()

    report = analyzer.analyze(synthetic_clinical_wound)
    assert report.is_valid_wound is True
    assert report.wound_area_px > 0
    assert report.lighting_analysis is None
    assert report.body_part is None


def test_headless_core_runs_without_dl_models_available(synthetic_clinical_wound):
    analyzer = ClinicalWoundAnalyzer()
    analyzer._dl_available = False
    analyzer._dl_model = None
    analyzer._resnet_available = False
    analyzer._resnet_classifier = None
    analyzer._ensemble_available = False
    analyzer._ensemble = None
    analyzer._wound_segmenter = None

    report = analyzer.analyze(synthetic_clinical_wound)
    assert report.is_valid_wound is True
    assert report.wound_area_px > 0
    assert report.dl_prediction is None
    assert report.resnet_prediction is None
    assert report.ensemble_classification is None
    assert report.primary_tissue
    assert len(report.tissues) == 4

