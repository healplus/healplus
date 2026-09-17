"""Validate synthetic operation resources against the pinned official FHIR R4 JSON schema.

Run from the repository root: python scripts/check_image_quality_fhir.py
Only the public HL7 schema is downloaded. No image or result is sent externally.
JSON Schema checks structure; this does not replace institutional profile validation.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import urllib.request
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import jsonschema

from src.image_quality.assessment import assess_image
from src.image_quality.decoder import decode_attachment
from src.image_quality.fhir import capability_statement, operation_definition, result_parameters
from tests.test_image_quality import attachment, payload, photograph

SCHEMA_URL = "https://hl7.org/fhir/R4/fhir.schema.json.zip"
SCHEMA_SHA256 = "2230406893b4cf002a4ee1e5e2bbeca22ac5d2d4931b3e9ef7b9594bbc376a01"


def main() -> None:
    with urllib.request.urlopen(SCHEMA_URL, timeout=60) as response:
        archive = response.read(8 * 1024 * 1024)
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        schema_bytes = zipped.read("fhir.schema.json")
    if hashlib.sha256(schema_bytes).hexdigest() != SCHEMA_SHA256:
        raise SystemExit("HL7 schema checksum changed; review the source before updating the pin.")
    schema = json.loads(schema_bytes)
    resources = [
        payload(),
        operation_definition(),
        capability_statement(),
        {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "error", "code": "invalid", "details": {"text": "Synthetic invalid input"}}],
        },
    ]
    for rgb in (photograph(), photograph() * 0):
        result = result_parameters(
            assess_image(decode_attachment(attachment(rgb))), "synthetic-image-001", str(uuid.uuid4())
        )
        resources.append(result)
        resources.append(next(p["resource"] for p in result["parameter"] if p["name"] == "measurement"))
    for resource in resources:
        specific = {**schema, "$ref": f"#/definitions/{resource['resourceType']}"}
        # The upstream root's oneOf is redundant after selecting the concrete resource.
        specific.pop("oneOf", None)
        jsonschema.Draft6Validator(specific).validate(resource)
    print(f"Validated {len(resources)} synthetic resources against official FHIR R4 4.0.1 JSON Schema.")


if __name__ == "__main__":
    main()
