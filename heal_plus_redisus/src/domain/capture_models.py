"""Persisted capture facts, independent of image processing or device inference.

Absent physical measurements remain unknown. A device orientation reading alone
does not establish the camera angle relative to the wound's anatomical plane.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator


class CaptureMeasurements(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False, revalidate_instances="always")

    distance_cm: float | None = Field(default=None, gt=0, le=500)
    distance_source: Literal["medida_manual", "sensor_calibrado"] | None = None
    angle_to_wound_plane_deg: float | None = Field(default=None, ge=0, le=180)
    angle_source: Literal["plano_medido_manualmente", "sensor_com_plano_calibrado"] | None = None
    scale_present: StrictBool | None = None
    scale_next_to_wound: StrictBool | None = None
    framing_complete: StrictBool | None = None
    neutral_background: StrictBool | None = None
    privacy_checked: StrictBool | None = None
    consent_to_capture: StrictBool | None = None
    identifying_exif_removed: StrictBool | None = None

    @model_validator(mode="after")
    def require_measurement_source(self) -> CaptureMeasurements:
        if (self.distance_cm is None) != (self.distance_source is None):
            raise ValueError("Distância exige medida e origem verificável.")
        if (self.angle_to_wound_plane_deg is None) != (self.angle_source is None):
            raise ValueError(
                "Ângulo exige referência medida ao plano da ferida; orientação do aparelho isolada não basta."
            )
        return self
