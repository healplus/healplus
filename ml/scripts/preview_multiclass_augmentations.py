"""Generate a local, opt-in grid of synchronized image/mask augmentations."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.multiclass_baseline import (  # noqa: E402
    augment_image_and_mask,
    letterbox_image_and_mask,
)
from src.training.segmentation_audit import (  # noqa: E402
    DatasetAuditConfig,
    discover_audit_samples,
)
from src.training.segmentation_review import (  # noqa: E402
    create_mask_overlay,
    load_review_image,
)
from src.training.tissue_taxonomy import load_tissue_taxonomy  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--sample-index", type=int, default=0)
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--taxonomy",
        type=Path,
        default=PROJECT_ROOT / "ml" / "configs" / "tissue_taxonomy_v0.json",
    )
    parser.add_argument("--allow-vertical-flip", action="store_true")
    parser.add_argument("--allow-local-clinical-previews", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.allow_local_clinical_previews:
        raise SystemExit(
            "Preview bloqueado. Confirme ambiente autorizado com "
            "--allow-local-clinical-previews."
        )
    if args.count < 20:
        raise SystemExit("--count deve ser pelo menos 20 para a revisão pré-treino.")

    taxonomy = load_tissue_taxonomy(args.taxonomy)
    samples, _ = discover_audit_samples(
        DatasetAuditConfig(
            dataset_root=args.dataset_root,
            manifest_path=args.manifest,
        )
    )
    if not 0 <= args.sample_index < len(samples):
        raise SystemExit("--sample-index está fora do conjunto auditado.")
    review_image = load_review_image(samples[args.sample_index], taxonomy)

    columns = 4
    rows = math.ceil(args.count / columns)
    figure, axes = plt.subplots(
        rows,
        columns,
        figsize=(columns * 3.2, rows * 3.2),
        squeeze=False,
    )
    for index, axis in enumerate(axes.ravel()):
        axis.axis("off")
        if index >= args.count:
            continue
        image, mask = augment_image_and_mask(
            review_image.image_rgb,
            review_image.mask,
            rng=np.random.default_rng(args.seed + index),
            allow_vertical_flip=args.allow_vertical_flip,
        )
        image, mask = letterbox_image_and_mask(
            image,
            mask,
            size=args.image_size,
        )
        axis.imshow(create_mask_overlay(image, mask, taxonomy))
        axis.set_title(f"variação {index + 1}")
    figure.suptitle(
        f"{review_image.sample_id} — revisão local de augmentations",
        fontsize=12,
    )
    figure.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=140)
    plt.close(figure)
    print(f"Grade local gerada com {args.count} variações.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
