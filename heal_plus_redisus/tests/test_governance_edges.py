"""Governance/privacy edge cases use synthetic inventory and image content only."""

from __future__ import annotations

import hashlib
import io
import struct
import zlib
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest
from PIL import Image, PngImagePlugin
from pydantic import ValidationError

from heal_plus_redisus.src import privacy
from heal_plus_redisus.src.experiment import (
    ExperimentManifest,
    ModelManifest,
    freeze_manifest,
    load_manifest,
    seed_experiment,
)

PACKAGE = Path(__file__).resolve().parents[1]


def manifest_data():
    return load_manifest(PACKAGE / "config" / "experiment_manifest.yaml").model_dump(mode="json")


def inventory(split, tone, index):
    return {
        "image_id": str(uuid4()),
        "patient_group": str(uuid4()),
        "split": split,
        "sha256": hashlib.sha256(str(index).encode()).hexdigest(),
        "width": 64,
        "height": 64,
        "skin_tone": tone,
    }


def available_manifest(*, kind="public", balanced=True):
    data = manifest_data()
    data["dataset"]["kind"] = kind
    data["model"].update(version="research-v1", status="experimental", checkpoint_sha256="f" * 64)
    data["items"] = [
        inventory(split, tone, index)
        for index, (split, tone) in enumerate(
            (split, tone)
            for split in ("train", "validation", "test")
            for tone in ("claro", "intermediario", "escuro_retinto")
        )
    ]
    if not balanced:
        data["items"] = [
            item for item in data["items"] if not (item["split"] == "test" and item["skin_tone"] == "escuro_retinto")
        ]
    return ExperimentManifest.model_validate(data)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), "NaN", "inf"])
def test_hyperparameters_reject_nonfinite_values(value):
    with pytest.raises(ValidationError):
        ModelManifest(
            architecture="UNet", version="untrained", status="unavailable", hyperparameters={"learning_rate": value}
        )


@pytest.mark.parametrize("value", [True, "42", 2.5, -1, 2**32])
def test_seed_is_strict_bounded_integer_in_manifest_and_runtime(value):
    data = manifest_data()
    data["seed"] = value
    with pytest.raises(ValidationError):
        ExperimentManifest.model_validate(data)
    with pytest.raises(ValueError):
        seed_experiment(value)


@pytest.mark.parametrize(
    "key,value",
    [
        ("api_key", "SYNTHETIC-KEY"),
        ("patient_name", "SYNTHETIC-NAME"),
        ("notes", "Synthetic clinical free text must not be a parameter"),
        ("optimizer", "sk-SYNTHETIC-NO-REAL-SECRET"),
    ],
)
def test_hyperparameters_reduce_accidental_credentials_and_free_text(key, value):
    with pytest.raises(ValidationError):
        ModelManifest(architecture="UNet", version="untrained", status="unavailable", hyperparameters={key: value})
    assert (
        ModelManifest(
            architecture="UNet",
            version="untrained",
            status="unavailable",
            hyperparameters={"optimizer": "adamw", "learning_rate": 0.001},
        ).hyperparameters["optimizer"]
        == "adamw"
    )


def test_unavailable_untrained_models_cannot_claim_weights_or_benchmark():
    with pytest.raises(ValidationError):
        ModelManifest(architecture="UNet", version="v1", status="unavailable", checkpoint_sha256="a" * 64)
    with pytest.raises(ValidationError):
        ModelManifest(architecture="UNet", version="untrained", status="experimental", checkpoint_sha256="a" * 64)
    data = manifest_data()
    data["items"] = [inventory("test", "claro", 1)]
    with pytest.raises(ValueError, match="pesos"):
        ExperimentManifest.model_validate(data).require_evaluable()


def test_evaluable_requires_skin_tone_representation_in_each_real_split():
    available_manifest().require_evaluable()
    with pytest.raises(ValueError, match="Cada split"):
        available_manifest(balanced=False).require_evaluable()
    available_manifest(kind="synthetic", balanced=False).require_evaluable()


def test_model_copy_cannot_bypass_validation_at_freeze_or_benchmark(tmp_path):
    manifest = available_manifest()
    invalid = manifest.model_copy(update={"seed": True})
    with pytest.raises(ValidationError):
        freeze_manifest(invalid, tmp_path / "invalid.json")
    assert not (tmp_path / "invalid.json").exists()
    with pytest.raises(ValidationError):
        invalid.require_evaluable()
    bad_model = manifest.model.model_copy(update={"hyperparameters": {"learning_rate": float("nan")}})
    with pytest.raises(ValidationError):
        freeze_manifest(manifest.model_copy(update={"model": bad_model}), tmp_path / "invalid-weights.json")


def test_freeze_does_not_overwrite_and_rejects_mutated_nested_parameters(tmp_path):
    manifest = available_manifest()
    target = tmp_path / "frozen.json"
    freeze_manifest(manifest, target)
    previous = target.read_bytes()
    with pytest.raises(FileExistsError):
        freeze_manifest(manifest, target)
    assert target.read_bytes() == previous
    manifest.model.hyperparameters["optimizer"] = "Clinical text must not be placed here"
    with pytest.raises(ValidationError):
        freeze_manifest(manifest, tmp_path / "mutated.json")


@pytest.mark.parametrize("different_split", [True, False])
def test_inventory_rejects_content_duplicates_and_cross_patient_hash_leakage(different_split):
    data = available_manifest().model_dump(mode="json")
    first = data["items"][0]
    data["items"].append(
        {
            **first,
            "image_id": str(uuid4()),
            "patient_group": str(uuid4()),
            "split": "test" if different_split else first["split"],
        }
    )
    with pytest.raises(ValidationError):
        ExperimentManifest.model_validate(data)


def test_real_governance_confirmations_are_strict_booleans():
    data = manifest_data()
    data["dataset"]["license_reviewed"] = "yes"
    with pytest.raises(ValidationError):
        ExperimentManifest.model_validate(data)


@pytest.mark.parametrize("consent,review", [(1, True), (True, 1), ("true", True), (True, "yes"), (False, False)])
def test_privacy_denial_precedes_decode(consent, review, monkeypatch):
    calls = []
    monkeypatch.setattr(privacy, "decode_attachment", lambda payload: calls.append(payload))
    with pytest.raises(PermissionError):
        privacy.sanitize_upload(b"synthetic", "image/png", consent=consent, privacy_reviewed=review)
    assert not calls


def test_upload_bytes_and_mime_limits_precede_decoder(monkeypatch):
    calls = []
    monkeypatch.setattr(privacy, "decode_attachment", lambda payload: calls.append(payload))
    for raw, mime in (
        (b"", "image/png"),
        (b"x" * (privacy.MAX_IMAGE_BYTES + 1), "image/png"),
        (b"small", "text/plain"),
    ):
        with pytest.raises(ValueError):
            privacy.sanitize_upload(raw, mime, consent=True, privacy_reviewed=True)
    assert not calls


def png_header(width, height):
    def chunk(kind, content):
        return (
            struct.pack(">I", len(content))
            + kind
            + content
            + struct.pack(">I", zlib.crc32(kind + content) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IEND", b"")
    )


def test_decoded_pixel_limit_is_enforced_before_pixel_allocation():
    with pytest.raises(ValueError, match="12 megapixels"):
        privacy.sanitize_upload(png_header(4000, 4000), "image/png", consent=True, privacy_reviewed=True)


def test_png_metadata_is_removed_from_persistable_content_and_pixels_preserved(tmp_path):
    rgb = np.random.default_rng(5).integers(0, 256, (32, 48, 3), dtype=np.uint8)
    info = PngImagePlugin.PngInfo()
    info.add_text("patient_identifier", "SYNTHETIC_IDENTIFIER_SENTINEL")
    info.add_itxt("comment", "SYNTHETIC_CLINICAL_SENTINEL")
    raw = io.BytesIO()
    Image.fromarray(rgb).save(raw, format="PNG", pnginfo=info)
    sanitized = privacy.sanitize_upload(raw.getvalue(), "image/png", consent=True, privacy_reviewed=True)
    persisted = tmp_path / "sanitized.png"
    persisted.write_bytes(sanitized.content)
    with Image.open(persisted) as decoded:
        assert not decoded.info and not decoded.getexif()
        assert np.array_equal(np.asarray(decoded), rgb)
    assert np.array_equal(sanitized.rgb, rgb)
    assert b"SYNTHETIC_" not in sanitized.content
    assert sanitized.sha256 == hashlib.sha256(persisted.read_bytes()).hexdigest()


def test_mime_mismatch_and_multiple_frames_are_rejected():
    frame = Image.new("RGB", (32, 32), (80, 70, 60))
    raw = io.BytesIO()
    frame.save(raw, format="PNG")
    with pytest.raises(ValueError):
        privacy.sanitize_upload(raw.getvalue(), "image/jpeg", consent=True, privacy_reviewed=True)
    animated = io.BytesIO()
    frame.save(
        animated,
        format="PNG",
        save_all=True,
        append_images=[Image.new("RGB", (32, 32), (90, 80, 70))],
        duration=100,
        loop=0,
    )
    with pytest.raises(ValueError, match="único quadro"):
        privacy.sanitize_upload(animated.getvalue(), "image/png", consent=True, privacy_reviewed=True)
