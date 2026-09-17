"""Audit a wound segmentation dataset without modifying source images or masks."""

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
    audit_segmentation_dataset,
    write_audit_outputs,
)
from src.training.tissue_taxonomy import load_tissue_taxonomy  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--image-dir", default="images")
    parser.add_argument("--mask-dir", default="masks")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--taxonomy",
        type=Path,
        default=PROJECT_ROOT / "ml" / "configs" / "tissue_taxonomy_v0.json",
    )
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "ml" / "outputs" / "segmentation_audit")
    parser.add_argument("--fail-on-blockers", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    taxonomy = load_tissue_taxonomy(args.taxonomy)
    config = DatasetAuditConfig(
        dataset_root=args.dataset_root,
        image_dir=args.image_dir,
        mask_dir=args.mask_dir,
        manifest_path=args.manifest,
    )
    report = audit_segmentation_dataset(config, taxonomy)
    outputs = write_audit_outputs(report, args.output_dir)
    print(
        json.dumps(
            {
                "summary": report["summary"],
                "release_blockers": report["release_blockers"],
                "outputs": outputs,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 2 if args.fail_on_blockers and report["release_blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

