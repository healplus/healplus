from __future__ import annotations

import json
from pathlib import Path

from .example_payloads import build_example_artifacts

SNAPSHOT_CONTRACT_VERSION = "2026-08-03"

SNAPSHOT_FILES = {
    "patient": "patient_example.json",
    "organization": "organization_example.json",
    "practitioner": "practitioner_example.json",
    "practitioner_role": "practitioner_role_example.json",
    "encounter": "encounter_example.json",
    "media": "media_example.json",
    "observation": "observation_example.json",
    "condition": "condition_example.json",
    "diagnostic_report": "diagnostic_report_example.json",
    "care_plan": "care_plan_example.json",
    "provenance": "provenance_example.json",
    "bundle": "wound_case_bundle.json",
}


def main() -> None:
    output_dir = Path(__file__).resolve().parent
    artifacts = build_example_artifacts()
    for artifact_name, filename in SNAPSHOT_FILES.items():
        (output_dir / filename).write_text(
            json.dumps(artifacts[artifact_name], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"Generated FHIR wound contract snapshots {SNAPSHOT_CONTRACT_VERSION}")


if __name__ == "__main__":
    main()
