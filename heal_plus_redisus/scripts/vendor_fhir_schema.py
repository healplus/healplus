"""Rebuild the offline export schema from checksum-pinned official HL7 R4."""

import hashlib
import io
import json
from pathlib import Path
import re
import urllib.request
import zipfile

URL = "https://hl7.org/fhir/R4/fhir.schema.json.zip"
SHA256 = "2230406893b4cf002a4ee1e5e2bbeca22ac5d2d4931b3e9ef7b9594bbc376a01"
KINDS = (
    "Patient",
    "Practitioner",
    "Condition",
    "Media",
    "Observation",
    "DiagnosticReport",
    "CarePlan",
    "Procedure",
    "Device",
    "DeviceUseStatement",
    "Provenance",
)


def main():
    with urllib.request.urlopen(URL, timeout=30) as response:
        archive = response.read(8 * 1024 * 1024)
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        raw = zipped.read("fhir.schema.json")
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise SystemExit("Upstream HL7 R4 checksum mismatch; review required.")
    source = json.loads(raw)
    definitions = source["definitions"]
    definitions["ResourceList"] = {"oneOf": [{"$ref": f"#/definitions/{name}"} for name in KINDS]}
    pending = ["Bundle", "ResourceList", *KINDS]
    selected = {}
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        selected[name] = definitions[name]
        pending.extend(re.findall(r'"\$ref": "#/definitions/([^"/]+)"', json.dumps(definitions[name])))
    schema = {
        "$schema": source["$schema"],
        "$comment": f"HL7 FHIR R4 4.0.1; source {URL}; original SHA256 {SHA256}. ResourceList restricted to sprint export resources; other definitions unchanged.",
        "definitions": selected,
    }
    path = Path(__file__).resolve().parents[1] / "config" / "fhir-export.schema.json"
    path.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Vendored {len(selected)} official R4 definitions, checksum verified.")


if __name__ == "__main__":
    main()
