"""Create deterministic patient-grouped folds without exposing raw identifiers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.segmentation_audit import (  # noqa: E402
    DatasetAuditConfig,
    discover_audit_samples,
)
from src.training.segmentation_splits import (  # noqa: E402
    SplitPreparationError,
    create_patient_grouped_folds,
    write_grouped_fold_outputs,
)
from src.training.tissue_taxonomy import load_tissue_taxonomy  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--taxonomy",
        type=Path,
        default=PROJECT_ROOT / "ml" / "configs" / "tissue_taxonomy_v0.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "ml" / "outputs" / "multiclass_folds",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    taxonomy = load_tissue_taxonomy(args.taxonomy)
    samples, orphan_masks = discover_audit_samples(
        DatasetAuditConfig(
            dataset_root=args.dataset_root,
            manifest_path=args.manifest,
        )
    )
    if orphan_masks:
        raise SystemExit("Split bloqueado: há máscaras sem imagens.")
    try:
        report = create_patient_grouped_folds(
            samples,
            taxonomy,
            n_splits=args.folds,
            seed=args.seed,
        )
    except SplitPreparationError as exc:
        raise SystemExit(f"Split bloqueado: {exc}") from exc
    outputs = write_grouped_fold_outputs(report, args.output_dir)
    print(
        json.dumps(
            {
                "summary": report["summary"],
                "warnings": report["warnings"],
                "outputs": outputs,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
