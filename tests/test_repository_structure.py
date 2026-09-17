from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HEAL_PLUS_ROOT = PROJECT_ROOT / "apps" / "heal_plus"
CONTRACTS_ROOT = PROJECT_ROOT / "contracts" / "heal_plus"


def test_heal_plus_has_one_canonical_application_root():
    assert (HEAL_PLUS_ROOT / "api" / "app.py").is_file()
    assert (HEAL_PLUS_ROOT / "web" / "package.json").is_file()
    assert not (PROJECT_ROOT / "web" / "redisus-frontend").exists()


def test_legacy_api_import_keeps_the_public_factory():
    from apps.api.app import create_app as legacy_create_app
    from apps.heal_plus.api.app import create_app

    assert legacy_create_app is create_app


def test_external_contracts_are_closed_and_versioned():
    schema_paths = sorted(CONTRACTS_ROOT.glob("*.schema.json"))

    assert {path.name for path in schema_paths} == {
        "fhir-message-envelope.schema.json",
        "image-validation-result.schema.json",
        "takere-image-reference.schema.json",
    }

    for schema_path in schema_paths:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["additionalProperties"] is False
        assert "contract_version" in schema["required"]
        assert schema["properties"]["contract_version"]["const"] == "1.0"


def test_image_reference_contract_does_not_accept_secrets_or_payloads():
    schema = json.loads(
        (CONTRACTS_ROOT / "takere-image-reference.schema.json").read_text(
            encoding="utf-8"
        )
    )

    properties = set(schema["properties"])
    assert properties.isdisjoint(
        {"authorization", "token", "signed_url", "patient_id", "image_bytes"}
    )
