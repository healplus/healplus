"""Technical capture protocol; physical distance and angle require measurements.

Pixel quality heuristics are configurable research checks, not a certification of
clinical usability. Absolute dark skin luminance is never a shadow criterion.
EXIF removal is performed by the ingestion boundary and explicitly confirmed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np

from ..domain.capture_models import CaptureMeasurements
from ..safety import ASSISTIVE_DISCLAIMER

CaptureStatus = Literal["aceito", "rejeitado", "indeterminado"]


@dataclass(frozen=True)
class CaptureThresholds:
    min_laplacian_variance: float = 60.0
    angle_tolerance_deg: float = 10.0
    max_highlight_fraction: float = 0.20
    relative_shadow_ratio: float = 0.35
    minimum_reference_pixels: int = 32

    def __post_init__(self) -> None:
        values = (
            self.min_laplacian_variance,
            self.angle_tolerance_deg,
            self.max_highlight_fraction,
            self.relative_shadow_ratio,
        )
        if not all(np.isfinite(value) and value >= 0 for value in values):
            raise ValueError("Limiares devem ser finitos e não negativos.")
        if self.max_highlight_fraction > 1 or self.relative_shadow_ratio > 1 or self.minimum_reference_pixels < 1:
            raise ValueError("Proporções devem estar em [0,1] e a referência deve conter pixels.")


@dataclass(frozen=True)
class CaptureCheck:
    code: str
    status: CaptureStatus
    message: str
    value: float | bool | None = None


@dataclass(frozen=True)
class CaptureValidation:
    status: CaptureStatus
    checks: tuple[CaptureCheck, ...]
    limitations: tuple[str, ...]
    disclaimer: str = ASSISTIVE_DISCLAIMER


class GuidedCaptureValidator:
    def __init__(self, thresholds: CaptureThresholds | None = None):
        self.thresholds = thresholds or CaptureThresholds()

    def validate(
        self,
        rgb: np.ndarray,
        measurements: CaptureMeasurements,
        *,
        perilesional_mask: np.ndarray | None = None,
    ) -> CaptureValidation:
        if (
            not isinstance(rgb, np.ndarray)
            or rgb.dtype != np.uint8
            or rgb.ndim != 3
            or rgb.shape[2] != 3
            or min(rgb.shape[:2]) < 32
        ):
            raise ValueError("Informe imagem RGB uint8 com pelo menos 32×32 pixels.")
        checks: list[CaptureCheck] = []
        height, width = rgb.shape[:2]
        central = rgb[height // 4 : 3 * height // 4, width // 4 : 3 * width // 4]
        factor = min(1.0, 512 / max(central.shape[:2]))
        if factor < 1:
            central = cv2.resize(central, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA)
        focus = float(cv2.Laplacian(cv2.cvtColor(central, cv2.COLOR_RGB2GRAY), cv2.CV_64F).var())
        focus_ok = focus >= self.thresholds.min_laplacian_variance
        checks.append(
            CaptureCheck(
                "F04",
                "aceito" if focus_ok else "rejeitado",
                "Nitidez técnica suficiente pelo limiar configurado."
                if focus_ok
                else "Imagem com pouca nitidez: toque sobre a ferida e mantenha a câmera firme; revise a captura.",
                focus,
            )
        )
        luminance = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)[:, :, 0].astype(np.float32)
        highlights = float(np.mean(np.all(rgb >= 250, axis=2)))
        if highlights > self.thresholds.max_highlight_fraction:
            checks.append(
                CaptureCheck(
                    "F03_reflexo",
                    "rejeitado",
                    "Há pixels saturados em excesso; evite flash direto e ajuste a iluminação.",
                    highlights,
                )
            )
        else:
            checks.append(
                CaptureCheck(
                    "F03_reflexo", "aceito", "Saturação branca abaixo do limiar técnico configurado.", highlights
                )
            )
        if perilesional_mask is None:
            checks.append(
                CaptureCheck(
                    "F03_relativa",
                    "indeterminado",
                    "Selecione referência de pele perilesional para revisar iluminação; tom escuro isolado não indica sombra.",
                )
            )
        else:
            mask = np.asarray(perilesional_mask)
            if mask.shape != (height, width) or mask.dtype != np.bool_:
                raise ValueError("A referência perilesional deve ser uma máscara booleana do tamanho da imagem.")
            reference = luminance[mask]
            if reference.size < self.thresholds.minimum_reference_pixels:
                checks.append(
                    CaptureCheck(
                        "F03_relativa",
                        "indeterminado",
                        "Referência perilesional insuficiente para comparar iluminação.",
                    )
                )
            else:
                low, high = np.percentile(reference, [10, 90])
                ratio = float(low / high) if high > 0 else None
                if ratio is None or np.mean(np.all(rgb[mask] == 0, axis=1)) > 0.95:
                    checks.append(
                        CaptureCheck(
                            "F03_relativa",
                            "indeterminado",
                            "Referência sem informação luminosa suficiente; revisar captura, sem inferir sombra pelo tom de pele.",
                            ratio,
                        )
                    )
                elif ratio < self.thresholds.relative_shadow_ratio and high - low > 65:
                    checks.append(
                        CaptureCheck(
                            "F03_relativa",
                            "indeterminado",
                            "Iluminação varia dentro da referência da própria pessoa; revisar sombra, pigmentação e luz indireta presencialmente.",
                            ratio,
                        )
                    )
                else:
                    checks.append(
                        CaptureCheck(
                            "F03_relativa",
                            "aceito",
                            "Referência perilesional sem grande variação relativa de iluminação pelo critério técnico.",
                            ratio,
                        )
                    )
        distance = measurements.distance_cm
        checks.append(
            CaptureCheck(
                "F01",
                "indeterminado" if distance is None else "aceito" if 20 <= distance <= 30 else "rejeitado",
                "Informe distância medida; pixels não permitem estimar centímetros."
                if distance is None
                else "Distância no intervalo de 20–30 cm."
                if 20 <= distance <= 30
                else "Ajuste a distância medida para 20–30 cm e inclua a pele ao redor.",
                distance,
            )
        )
        angle = measurements.angle_to_wound_plane_deg
        angle_ok = angle is not None and abs(angle - 90) <= self.thresholds.angle_tolerance_deg
        checks.append(
            CaptureCheck(
                "F02",
                "indeterminado" if angle is None else "aceito" if angle_ok else "rejeitado",
                "Informe ângulo em relação ao plano da ferida; o sensor do aparelho isolado não determina esse plano."
                if angle is None
                else "Ângulo frontal dentro da tolerância técnica de 90°."
                if angle_ok
                else "Reposicione a câmera de forma frontal, perpendicular ao plano da ferida (90°).",
                angle,
            )
        )
        for field, code, message in (
            ("scale_present", "F06", "Posicione escala métrica limpa junto da lesão."),
            ("scale_next_to_wound", "F06_posicao", "Confirme que a escala fica ao lado, sem cobrir leito ou borda."),
            (
                "framing_complete",
                "F01_enquadramento",
                "Inclua a lesão inteira, borda e margem perilesional necessária.",
            ),
            ("neutral_background", "F05", "Use fundo liso e neutro."),
            ("privacy_checked", "F07", "Confirme ausência de rosto, etiquetas e identificadores desnecessários."),
            ("consent_to_capture", "consentimento", "Registre consentimento para esta captura antes de prosseguir."),
            (
                "identifying_exif_removed",
                "exif",
                "Remova metadados identificáveis no fluxo de ingestão antes de persistir a imagem.",
            ),
        ):
            value = getattr(measurements, field)
            checks.append(
                CaptureCheck(
                    code,
                    "indeterminado" if value is None else "aceito" if value else "rejeitado",
                    message if value is not True else "Confirmação do protocolo registrada.",
                    value,
                )
            )
        status: CaptureStatus = (
            "rejeitado"
            if any(check.status == "rejeitado" for check in checks)
            else "indeterminado"
            if any(check.status == "indeterminado" for check in checks)
            else "aceito"
        )
        return CaptureValidation(
            status,
            tuple(checks),
            (
                "Aceitação se refere apenas ao protocolo técnico configurado; não valida uso ou interpretação clínica.",
                "Limiares de nitidez e iluminação precisam de calibração por câmera, resolução e população antes de uso assistencial.",
                "Distância, ângulo, escala, consentimento e privacidade dependem de medidas ou confirmação explícita; não são inferidos da fotografia.",
            ),
        )
