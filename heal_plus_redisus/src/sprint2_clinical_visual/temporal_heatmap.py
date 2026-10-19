"""Conservative planar longitudinal comparison with independent metric scales.

Landmarks must represent corresponding anatomy, verified by a professional. A
robust homography only supports approximately planar, comparable photographs;
it cannot correct a cavity, substantial perspective/deformation, or prove healing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import cv2
import numpy as np

from ..safety import ASSISTIVE_DISCLAIMER


@dataclass(frozen=True)
class ScaleCalibration:
    reference_length: float
    reference_pixels: float
    unit: Literal["mm", "cm"] = "mm"
    verified_by: str = ""
    same_plane_as_wound: bool = False

    @property
    def mm_per_pixel(self) -> float:
        if self.unit not in {"mm", "cm"} or not self.verified_by or not self.same_plane_as_wound:
            raise ValueError("Calibração exige unidade mm/cm, revisão e escala no mesmo plano da ferida.")
        if not all(np.isfinite(value) and value > 0 for value in (self.reference_length, self.reference_pixels)):
            raise ValueError("Comprimento e pixels da escala devem ser positivos e finitos.")
        return self.reference_length * (10 if self.unit == "cm" else 1) / self.reference_pixels


@dataclass(frozen=True)
class TemporalFrame:
    patient_id: str
    wound_id: str
    captured_at: datetime
    labels: np.ndarray
    roi_mask: np.ndarray
    uncertainty_mask: np.ndarray
    calibration: ScaleCalibration | None = None
    intervention: Literal["nenhuma_registrada", "pre_desbridamento", "pos_desbridamento", "outra", "desconhecida"] = (
        "desconhecida"
    )


@dataclass(frozen=True)
class AlignmentEvidence:
    current_points: np.ndarray
    previous_points: np.ndarray
    verified_by: str
    approximately_planar: bool


@dataclass(frozen=True)
class TissueSummary:
    roi_pixels: int
    uncertain_pixels: int
    uncertainty_fraction: float
    roi_area_mm2: float
    confident_area_mm2: float
    confident_tissue_fractions: dict[int, float | None]


@dataclass(frozen=True)
class TemporalComparison:
    status: Literal["comparavel", "indeterminado"]
    reason: str
    previous: TissueSummary | None = None
    current: TissueSummary | None = None
    area_change_mm2: float | None = None
    compared_pixels: int = 0
    changed_tissue_pixels: int = 0
    heatmap_rgb: np.ndarray | None = None
    comparison_mask: np.ndarray | None = None
    homography_current_to_previous: np.ndarray | None = None
    inlier_fraction: float | None = None
    median_reprojection_error_px: float | None = None
    contextual_notes: tuple[str, ...] = ()
    disclaimer: str = ASSISTIVE_DISCLAIMER


class TemporalHeatmap:
    """Render categorical differences; colours do not rank clinical improvement."""

    def __init__(
        self,
        *,
        max_reprojection_error_px: float = 3.0,
        minimum_inlier_fraction: float = 0.75,
        scale_relative_tolerance: float = 0.20,
    ):
        if not np.isfinite(max_reprojection_error_px) or max_reprojection_error_px <= 0:
            raise ValueError("Erro de reprojeção deve ser positivo e finito.")
        if not 0 < minimum_inlier_fraction <= 1 or not 0 < scale_relative_tolerance <= 1:
            raise ValueError("Proporções de alinhamento devem estar em (0,1].")
        self.max_reprojection_error_px = max_reprojection_error_px
        self.minimum_inlier_fraction = minimum_inlier_fraction
        self.scale_relative_tolerance = scale_relative_tolerance

    def compare(
        self, previous: TemporalFrame, current: TemporalFrame, alignment: AlignmentEvidence | None
    ) -> TemporalComparison:
        for frame in (previous, current):
            self._validate_frame(frame)
        if previous.patient_id != current.patient_id or previous.wound_id != current.wound_id:
            raise ValueError("Comparação exige a mesma pessoa e a mesma ferida.")
        if current.captured_at <= previous.captured_at:
            raise ValueError("A avaliação atual deve ser posterior à avaliação anterior.")
        notes = [
            "Diferenças indicam mudança observada; não demonstram cura, piora, diagnóstico ou resposta causal ao tratamento."
        ]
        if previous.intervention == "desconhecida" or current.intervention == "desconhecida":
            notes.append(
                "Contexto de intervenções incompleto; confirmar desbridamento e outras mudanças entre as visitas."
            )
        if "pos_desbridamento" in (previous.intervention, current.intervention):
            notes.append(
                "Registro pós-desbridamento: aumento de área aparente ou mudança tecidual pode refletir a intervenção e exige interpretação profissional."
            )
        if previous.calibration is None or current.calibration is None:
            return TemporalComparison(
                "indeterminado",
                "Cada visita exige calibração métrica independente no plano da ferida.",
                contextual_notes=tuple(notes),
            )
        prior_scale, new_scale = previous.calibration.mm_per_pixel, current.calibration.mm_per_pixel
        prior_summary, new_summary = self._summary(previous, prior_scale), self._summary(current, new_scale)

        def unavailable(
            reason: str,
            *,
            inlier_fraction: float | None = None,
            median_reprojection_error_px: float | None = None,
        ) -> TemporalComparison:
            return TemporalComparison(
                "indeterminado",
                reason,
                prior_summary,
                new_summary,
                contextual_notes=tuple(notes),
                inlier_fraction=inlier_fraction,
                median_reprojection_error_px=median_reprojection_error_px,
            )

        if alignment is None or not alignment.verified_by or not alignment.approximately_planar:
            return unavailable(
                "Forneça correspondências anatômicas revisadas e confirme comparabilidade aproximadamente planar."
            )
        source = np.asarray(alignment.current_points, dtype=np.float64)
        target = np.asarray(alignment.previous_points, dtype=np.float64)
        if (
            source.shape != target.shape
            or source.ndim != 2
            or source.shape[1] != 2
            or len(source) < 6
            or not np.all(np.isfinite(source))
            or not np.all(np.isfinite(target))
        ):
            raise ValueError("Alinhamento robusto exige pelo menos seis pares de pontos 2D finitos.")
        for points, frame in ((source, current), (target, previous)):
            height, width = frame.labels.shape
            if np.any(points < 0) or np.any(points[:, 0] >= width) or np.any(points[:, 1] >= height):
                raise ValueError("Correspondências devem ficar dentro da respectiva imagem.")
            if (
                len(np.unique(points, axis=0)) < 6
                or cv2.contourArea(cv2.convexHull(points.astype(np.float32))) < height * width * 0.01
            ):
                return unavailable(
                    "Correspondências degeneradas ou concentradas; marque pontos distribuídos ao redor da ferida."
                )
        homography, inliers = cv2.findHomography(source, target, cv2.RANSAC, self.max_reprojection_error_px)
        if homography is None or inliers is None or not np.all(np.isfinite(homography)):
            return unavailable("Não foi possível estimar alinhamento robusto.")
        fraction = float(inliers.mean())
        projected = cv2.perspectiveTransform(source.reshape(-1, 1, 2), homography).reshape(-1, 2)
        errors = np.linalg.norm(projected - target, axis=1)
        reprojection = float(np.median(errors[inliers.ravel().astype(bool)]))
        if fraction < self.minimum_inlier_fraction or reprojection > self.max_reprojection_error_px:
            return unavailable(
                "Alinhamento com correspondências insuficientes ou erro elevado.",
                inlier_fraction=fraction,
                median_reprojection_error_px=reprojection,
            )
        # Independent physical scale checks prevent an otherwise plausible fit
        # from silently manufacturing a dimensional change.
        cy, cx = np.array(current.labels.shape) / 2
        probes = np.array([[[cx, cy]], [[cx + 1, cy]], [[cx, cy + 1]]], dtype=np.float64)
        mapped = cv2.perspectiveTransform(probes, homography).reshape(-1, 2)
        jacobian = np.column_stack((mapped[1] - mapped[0], mapped[2] - mapped[0]))
        expected = new_scale / prior_scale
        singular = np.linalg.svd(jacobian, compute_uv=False)
        if np.linalg.det(jacobian) <= 0 or np.any(np.abs(singular / expected - 1) > self.scale_relative_tolerance):
            return unavailable(
                "Transformação incompatível com as escalas métricas ou orientação; repetir captura/calibração.",
                inlier_fraction=fraction,
                median_reprojection_error_px=reprojection,
            )
        size = (previous.labels.shape[1], previous.labels.shape[0])

        def warp(mask: np.ndarray) -> np.ndarray:
            return cv2.warpPerspective(
                mask.astype(np.uint8),
                homography,
                size,
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            ).astype(bool)

        footprint = warp(np.ones(current.labels.shape, dtype=bool))
        roi_current = warp(current.roi_mask)
        uncertain_current = warp(current.uncertainty_mask | (current.labels == 4))
        labels_current = cv2.warpPerspective(
            current.labels.astype(np.uint8),
            homography,
            size,
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=4,
        )
        valid_prior = previous.roi_mask & ~previous.uncertainty_mask & (previous.labels != 4)
        valid_current = roi_current & ~uncertain_current & (labels_current != 4)
        comparison = valid_prior & valid_current & footprint
        if not np.any(comparison):
            return unavailable(
                "Sem região alinhada com confiança suficiente em ambas as visitas.",
                inlier_fraction=fraction,
                median_reprojection_error_px=reprojection,
            )
        changed = comparison & (previous.labels != labels_current)
        appeared = valid_current & ~previous.roi_mask & footprint & ~previous.uncertainty_mask
        disappeared = valid_prior & ~roi_current & footprint & ~uncertain_current
        heatmap = np.zeros((*previous.labels.shape, 3), dtype=np.uint8)
        heatmap[comparison] = (100, 100, 100)
        heatmap[changed] = (148, 80, 210)
        heatmap[appeared] = (35, 145, 200)
        heatmap[disappeared] = (230, 165, 55)
        notes.append(
            "Legenda: cinza=mesma classe; violeta=classe diferente; azul=ROI atual adicional; ocre=ROI anterior sem correspondência atual; preto=fora da comparação ou baixa confiança."
        )
        return TemporalComparison(
            "comparavel",
            "Comparação técnica disponível nas regiões alinhadas com confiança suficiente.",
            prior_summary,
            new_summary,
            new_summary.roi_area_mm2 - prior_summary.roi_area_mm2,
            int(comparison.sum()),
            int(changed.sum()),
            heatmap,
            comparison,
            homography,
            fraction,
            reprojection,
            tuple(notes),
        )

    @staticmethod
    def _validate_frame(frame: TemporalFrame) -> None:
        if not frame.patient_id or not frame.wound_id or frame.captured_at.utcoffset() is None:
            raise ValueError("Informe identificadores pseudonimizados e data com fuso horário.")
        labels = np.asarray(frame.labels)
        if labels.ndim != 2 or not np.issubdtype(labels.dtype, np.integer) or min(labels.shape, default=0) < 2:
            raise ValueError("Mapa de classes deve ser uma matriz inteira não vazia.")
        for mask in (frame.roi_mask, frame.uncertainty_mask):
            if not isinstance(mask, np.ndarray) or mask.dtype != np.bool_ or mask.shape != labels.shape:
                raise ValueError("Máscaras ROI e incerteza devem ser booleanas e coincidir com as classes.")
        if not np.any(frame.roi_mask) or not np.isin(labels[frame.roi_mask], [0, 1, 2, 3, 4]).all():
            raise ValueError("ROI exige pixels e classes 0–4; classe 4 representa baixa confiança.")

    @staticmethod
    def _summary(frame: TemporalFrame, mm_per_pixel: float) -> TissueSummary:
        uncertain = frame.roi_mask & (frame.uncertainty_mask | (frame.labels == 4))
        confident = frame.roi_mask & ~uncertain
        total, excluded, known = int(frame.roi_mask.sum()), int(uncertain.sum()), int(confident.sum())
        return TissueSummary(
            total,
            excluded,
            excluded / total,
            total * mm_per_pixel**2,
            known * mm_per_pixel**2,
            {
                label: float(np.sum(confident & (frame.labels == label))) / known if known else None
                for label in range(4)
            },
        )
