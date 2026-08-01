"""Calculate agreement for two independent multiclass wound annotations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.annotation_agreement import (  # noqa: E402
    evaluate_annotation_agreement,
    load_annotation_pairs,
    write_agreement_outputs,
)
from src.training.tissue_taxonomy import load_tissue_taxonomy  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument(
        "--taxonomy",
        type=Path,
        default=PROJECT_ROOT / "ml" / "configs" / "tissue_taxonomy_v0.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "ml" / "outputs" / "annotation_agreement",
    )
    parser.add_argument("--fail-on-invalid-pairs", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    taxonomy = load_tissue_taxonomy(args.taxonomy)
    pairs = load_annotation_pairs(args.manifest, args.dataset_root)
    report = evaluate_annotation_agreement(pairs, taxonomy)
    outputs = write_agreement_outputs(report, args.output_dir)
    print(
        json.dumps(
            {
                "summary": report["summary"],
                "blockers": report["blockers"],
                "outputs": outputs,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 2 if args.fail_on_invalid_pairs and report["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
