"""Versioned, explainable heuristics; thresholds await external RUTE calibration."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import cv2
import numpy as np

from .decoder import DecodedImage

ALGORITHM_VERSION = "healplus-iqa-1.0.0"
LIMITATION = (
    "Avaliação técnica experimental, sem validação clínica. Não confirma presença de ferida, "
    "fidelidade de cor, enquadramento ou adequação diagnóstica. Requer revisão profissional."
)


@dataclass(frozen=True)
class QualityPolicy:
    min_short_side: int = 480
    min_long_side: int = 640
    analysis_long_side: int = 1024
    min_sharpness: float = 45.0
    review_sharpness: float = 90.0
    min_brightness: float = 35.0
    max_brightness: float = 220.0
    max_dark_fraction: float = 0.35
    max_bright_fraction: float = 0.20
    min_contrast: float = 25.0
    max_glare_fraction: float = 0.05
    max_lighting_spread: float = 0.35
    max_noise: float = 12.0


POLICY = QualityPolicy()


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class Assessment:
    status: str
    metrics: dict[str, float]
    findings: tuple[Finding, ...]


def assess_image(image: DecodedImage) -> Assessment:
    rgb = image.rgb
    scale = min(1.0, POLICY.analysis_long_side / max(image.width, image.height))
    if scale < 1:
        rgb = cv2.resize(
            rgb, (max(1, round(image.width * scale)), max(1, round(image.height * scale))), interpolation=cv2.INTER_AREA
        )
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    smoothed = cv2.GaussianBlur(gray, (3, 3), 0.5)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    tiles = [tile for row in np.array_split(gray, 3, axis=0) for tile in np.array_split(row, 3, axis=1) if tile.size]
    tile_means = [float(tile.mean()) for tile in tiles]
    # Estimate high-frequency residual on lower-gradient pixels to reduce edge contamination.
    residual = np.abs(gray.astype(np.float32) - cv2.medianBlur(gray, 3).astype(np.float32))
    gradient = cv2.magnitude(cv2.Sobel(smoothed, cv2.CV_32F, 1, 0), cv2.Sobel(smoothed, cv2.CV_32F, 0, 1))
    low_gradient = gradient <= np.percentile(gradient, 50)
    metrics = {
        "width": float(image.width),
        "height": float(image.height),
        "analysis-width": float(rgb.shape[1]),
        "analysis-height": float(rgb.shape[0]),
        "sharpness": float(cv2.Laplacian(smoothed, cv2.CV_64F).var()),
        "brightness": float(gray.mean()),
        "dark-fraction": float(np.mean(gray <= 15)),
        "bright-fraction": float(np.mean(gray >= 245)),
        "contrast": float(np.percentile(gray, 95) - np.percentile(gray, 5)),
        "glare-fraction": float(np.mean((hsv[:, :, 2] >= 245) & (hsv[:, :, 1] <= 30))),
        "lighting-spread": (max(tile_means) - min(tile_means)) / 255.0,
        "noise": float(np.median(residual[low_gradient])),
    }
    findings: list[Finding] = []

    def flag(condition: bool, code: str, severity: str, message: str) -> None:
        if condition:
            findings.append(Finding(code, severity, message))

    flag(
        min(image.width, image.height) < POLICY.min_short_side or max(image.width, image.height) < POLICY.min_long_side,
        "low-resolution",
        "error",
        "Capture novamente com pelo menos 640 × 480 pixels, sem ampliar artificialmente.",
    )
    flag(
        metrics["sharpness"] < POLICY.min_sharpness,
        "blur",
        "error",
        "Estabilize a câmera e refaça o foco antes de capturar.",
    )
    flag(
        POLICY.min_sharpness <= metrics["sharpness"] < POLICY.review_sharpness,
        "borderline-focus",
        "warning",
        "Confira o foco na região de interesse e considere repetir a captura.",
    )
    flag(
        metrics["brightness"] < POLICY.min_brightness or metrics["dark-fraction"] > POLICY.max_dark_fraction,
        "underexposure",
        "error",
        "Melhore a iluminação difusa e repita a captura, evitando sombras intensas.",
    )
    flag(
        metrics["brightness"] > POLICY.max_brightness or metrics["bright-fraction"] > POLICY.max_bright_fraction,
        "overexposure",
        "error",
        "Reduza a luz direta ou a exposição e repita a captura.",
    )
    flag(
        metrics["contrast"] < POLICY.min_contrast,
        "low-contrast",
        "error",
        "Confira iluminação e lente; capture novamente preservando detalhes.",
    )
    flag(
        metrics["glare-fraction"] > POLICY.max_glare_fraction,
        "possible-glare",
        "warning",
        "Confira áreas claras sem detalhes; ajuste o ângulo da luz se houver reflexos.",
    )
    flag(
        metrics["lighting-spread"] > POLICY.max_lighting_spread,
        "uneven-lighting",
        "warning",
        "Confira sombras e distribuição da luz na região de interesse.",
    )
    flag(
        metrics["noise"] > POLICY.max_noise,
        "possible-noise",
        "warning",
        "Confira granulação; aumente a luz difusa e evite zoom digital.",
    )
    flag(
        image.monochrome,
        "monochrome",
        "warning",
        "Envie a fotografia original em cores para permitir revisão profissional.",
    )
    status = "rejected" if any(f.severity == "error" for f in findings) else "indeterminate" if findings else "accepted"
    return Assessment(status, {key: round(value, 6) for key, value in metrics.items()}, tuple(findings))


def policy_values() -> dict[str, int | float]:
    return asdict(POLICY)
