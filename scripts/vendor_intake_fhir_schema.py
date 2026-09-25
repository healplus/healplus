"""Extract the intake resource subset of the checksum-pinned HL7 FHIR R4 schema."""

import hashlib
import io
import json
from pathlib import Path
import re
import urllib.request
import zipfile

URL = "https://hl7.org/fhir/R4/fhir.schema.json.zip"
SHA256 = "2230406893b4cf002a4ee1e5e2bbeca22ac5d2d4931b3e9ef7b9594bbc376a01"
TARGET = Path(__file__).resolve().parents[1] / "src/analysis_intake/fhir-r4.schema.json"


def main():
    with urllib.request.urlopen(URL, timeout=30) as response:
        archive = response.read(8 * 1024 * 1024)
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        raw = zipped.read("fhir.schema.json")
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise SystemExit("Upstream schema checksum mismatch")
    source = json.loads(raw)
    definitions = source["definitions"]
    names = {"Bundle", "Media", "Patient", "Encounter", "Task"}
    definitions["ResourceList"] = {"oneOf": [{"$ref": f"#/definitions/{n}"} for n in sorted(names)]}
    pending = sorted(names | {"ResourceList"})
    selected = {}
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        selected[name] = definitions[name]
        pending.extend(re.findall(r'"\$ref": "#/definitions/([^"/]+)"', json.dumps(definitions[name])))
    schema = {
        "$schema": source["$schema"],
        "$comment": f"HL7 FHIR R4 4.0.1; source {URL}; SHA256 {SHA256}. ResourceList restricted to intake resources; other definitions unchanged.",
        "definitions": selected,
    }
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Vendored {len(selected)} definitions")


if __name__ == "__main__":
    main()
