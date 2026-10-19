"""Descriptive factor audit with explicit missingness and stratified denominators.

The prevalence ratio compares a factor in preselected failure/control samples.
It is not a causal effect, a population risk ratio, or clinical validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from statistics import mean
from typing import Iterable

from ..safety import ASSISTIVE_DISCLAIMER
from .visual_inspector import FEATURE_CATALOG, ObservationState, SkinTone, VisualInspection


@dataclass(frozen=True)
class Frequency:
    present: int
    observed: int
    unknown: int
    total: int
    proportion: float | None


@dataclass(frozen=True)
class MetricSummary:
    count: int
    mean: float | None


@dataclass(frozen=True)
class FeatureComparison:
    code: str
    label: str
    failure: Frequency
    control: Frequency
    prevalence_ratio: float | None
    ratio_status: str
    dice_with_factor: MetricSummary
    iou_with_factor: MetricSummary
    tia_with_factor: MetricSummary
    dice_without_factor: MetricSummary
    iou_without_factor: MetricSummary
    tia_without_factor: MetricSummary


@dataclass(frozen=True)
class EquitySummary:
    sample_count: int
    dice: MetricSummary
    iou: MetricSummary
    tia: MetricSummary
    necrosis_false_positive_rate: float | None
    necrosis_reference_pixels: int
    erythema_false_negative_rate: float | None
    erythema_reference_pixels: int


@dataclass(frozen=True)
class CombinationComparison:
    codes: tuple[str, str]
    failure: Frequency
    control: Frequency
    prevalence_ratio: float | None


@dataclass(frozen=True)
class StatisticalReport:
    failure_categories: tuple[str, ...]
    failure_count: int
    control_count: int
    excluded_unreviewed: int
    comparisons: tuple[FeatureComparison, ...]
    combinations: tuple[CombinationComparison, ...]
    by_skin_tone: dict[str, tuple[FeatureComparison, ...]]
    by_dataset: dict[str, tuple[FeatureComparison, ...]]
    equity_by_skin_tone: dict[str, EquitySummary]
    limitations: tuple[str, ...]
    disclaimer: str = ASSISTIVE_DISCLAIMER


def _metric(records: list[VisualInspection], field: str) -> MetricSummary:
    values = [getattr(row, field) for row in records if getattr(row, field) is not None]
    return MetricSummary(len(values), mean(values) if values else None)


def _frequency(records: list[VisualInspection], codes: tuple[str, ...]) -> Frequency:
    # For combinations, an explicit absence establishes absence even if another
    # factor is unknown. Presence requires every factor to be present.
    states = [[row.state(code) for code in codes] for row in records]
    present = sum(all(value == ObservationState.PRESENT for value in row) for row in states)
    absent = sum(ObservationState.ABSENT in row for row in states)
    observed = present + absent
    return Frequency(present, observed, len(records) - observed, len(records), present / observed if observed else None)


def _ratio(failure: Frequency, control: Frequency) -> tuple[float | None, str]:
    if failure.proportion is None or control.proportion is None:
        return None, "indeterminado_sem_observacoes"
    if control.proportion == 0:
        return None, "indeterminado_denominador_zero"
    return failure.proportion / control.proportion, "calculado_descritivo"


class StatisticalAnalyzer:
    """Compare category D with A by default; opt into C/D/E explicitly.

    Unknown/not-assessed values are reported, never counted as absence. Only
    professional-reviewed annotations contribute by default. Dataset and skin
    strata expose composition differences rather than silently pooling them.
    """

    def analyze(
        self,
        records: Iterable[VisualInspection],
        *,
        failure_categories: tuple[str, ...] = ("D",),
        require_review: bool = True,
    ) -> StatisticalReport:
        if not failure_categories or not set(failure_categories).issubset({"B", "C", "D", "E"}):
            raise ValueError("Informe categorias de falha B/C/D/E sem incluir o controle A.")
        rows = list(records)
        keys = [(row.dataset_id, row.image_id) for row in rows]
        if len(keys) != len(set(keys)):
            raise ValueError("Uma imagem não pode aparecer mais de uma vez no mesmo dataset.")

        def is_failure(row: VisualInspection) -> bool:
            return row.category in failure_categories or (
                "E" in failure_categories and row.tia is not None and row.tia >= 0.35
            )

        selected = [row for row in rows if row.category == "A" or is_failure(row)]
        excluded = sum(row.reviewer_id is None for row in selected) if require_review else 0
        selected = [row for row in selected if not require_review or row.reviewer_id is not None]
        failures = [row for row in selected if is_failure(row)]
        controls = [row for row in selected if row.category == "A" and not is_failure(row)]
        compare = self._compare(failures, controls)
        combos = []
        for codes in combinations(FEATURE_CATALOG, 2):
            freq_f, freq_c = _frequency(failures, codes), _frequency(controls, codes)
            if freq_f.present or freq_c.present:
                combos.append(CombinationComparison(codes, freq_f, freq_c, _ratio(freq_f, freq_c)[0]))
        by_skin = {
            tone.value: self._compare(
                [row for row in failures if row.skin_tone == tone],
                [row for row in controls if row.skin_tone == tone],
            )
            for tone in SkinTone
        }
        by_dataset = {
            dataset: self._compare(
                [row for row in failures if row.dataset_id == dataset],
                [row for row in controls if row.dataset_id == dataset],
            )
            for dataset in sorted({row.dataset_id for row in selected})
        }
        equity = {tone.value: self._equity([row for row in selected if row.skin_tone == tone]) for tone in SkinTone}
        return StatisticalReport(
            tuple(dict.fromkeys(failure_categories)),
            len(failures),
            len(controls),
            excluded,
            compare,
            tuple(combos),
            by_skin,
            by_dataset,
            equity,
            (
                "Análise descritiva de grupos selecionados; não demonstra causalidade ou risco populacional.",
                "Frequências usam somente observações presentes/ausentes; totais e desconhecidos são apresentados separadamente.",
                "Ausência de amostras, referência clínica ou denominador resulta em valor indeterminado.",
                "Comparabilidade, pareamento e representatividade clínica precisam de revisão por equipe de pesquisa e saúde.",
            ),
        )

    @staticmethod
    def _compare(failures: list[VisualInspection], controls: list[VisualInspection]) -> tuple[FeatureComparison, ...]:
        all_rows = failures + controls
        result = []
        for code, definition in FEATURE_CATALOG.items():
            freq_f, freq_c = _frequency(failures, (code,)), _frequency(controls, (code,))
            ratio, status = _ratio(freq_f, freq_c)
            with_factor = [row for row in all_rows if row.state(code) == ObservationState.PRESENT]
            without = [row for row in all_rows if row.state(code) == ObservationState.ABSENT]
            result.append(
                FeatureComparison(
                    code,
                    definition.label,
                    freq_f,
                    freq_c,
                    ratio,
                    status,
                    *(_metric(with_factor, field) for field in ("dice", "detector_iou", "tia")),
                    *(_metric(without, field) for field in ("dice", "detector_iou", "tia")),
                )
            )
        return tuple(result)

    @staticmethod
    def _equity(rows: list[VisualInspection]) -> EquitySummary:
        necrosis_counts: list[tuple[int, int]] = []
        erythema_counts: list[tuple[int, int]] = []
        for row in rows:
            counts = row.equity_counts
            if counts.non_necrosis_reference_pixels is not None and counts.necrosis_false_positive_pixels is not None:
                necrosis_counts.append((counts.necrosis_false_positive_pixels, counts.non_necrosis_reference_pixels))
            if counts.erythema_reference_pixels is not None and counts.erythema_false_negative_pixels is not None:
                erythema_counts.append((counts.erythema_false_negative_pixels, counts.erythema_reference_pixels))
        necrosis_denominator = sum(denominator for _, denominator in necrosis_counts)
        erythema_denominator = sum(denominator for _, denominator in erythema_counts)
        return EquitySummary(
            len(rows),
            _metric(rows, "dice"),
            _metric(rows, "detector_iou"),
            _metric(rows, "tia"),
            sum(numerator for numerator, _ in necrosis_counts) / necrosis_denominator if necrosis_denominator else None,
            necrosis_denominator,
            sum(numerator for numerator, _ in erythema_counts) / erythema_denominator if erythema_denominator else None,
            erythema_denominator,
        )
