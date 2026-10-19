"""Sprint 1 public contracts; optional PyTorch adapter lives in ``neural``."""

from .roi_handler import ROI, ROIHandler, TriadZones, triad_zones
from .hybrid_segmenter import HybridSegmenter, NeuralPrediction, SegmentationResult, TISSUE_CLASSES
from .cascade_evaluator import CascadeEvaluator, CascadeEvaluation, EvaluationRecord, YoloDetectorAdapter

__all__ = [
    "ROI",
    "ROIHandler",
    "TriadZones",
    "triad_zones",
    "HybridSegmenter",
    "NeuralPrediction",
    "SegmentationResult",
    "TISSUE_CLASSES",
    "CascadeEvaluator",
    "CascadeEvaluation",
    "EvaluationRecord",
    "YoloDetectorAdapter",
]
