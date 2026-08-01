"""Train the first multiclass U-Net only after governance and leakage gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.multiclass_baseline import (  # noqa: E402
    MulticlassBaselineConfig,
    MulticlassBaselineError,
    train_multiclass_baseline,
)
from src.training.segmentation_audit import (  # noqa: E402
    DatasetAuditConfig,
    audit_segmentation_dataset,
    discover_audit_samples,
)
from src.training.tissue_taxonomy import load_tissue_taxonomy  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--fold-assignments", required=True, type=Path)
    parser.add_argument("--validation-fold", type=int, required=True)
    parser.add_argument(
        "--taxonomy",
        type=Path,
        default=PROJECT_ROOT / "ml" / "configs" / "tissue_taxonomy_v0.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "ml" / "outputs" / "multiclass_unet_v0",
    )
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--base-channels", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument(
        "--loss",
        choices=["cross_entropy_dice", "focal_dice", "focal_tversky"],
        default="cross_entropy_dice",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--accept-research-only", action="store_true")
    return parser.parse_args()


def _load_fold_assignments(path: Path) -> dict[str, int]:
    import csv

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    try:
        return {
            str(row["sample_id"]): int(row["fold"])
            for row in rows
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise SystemExit("Arquivo de folds inválido; esperado sample_id,fold.") from exc


def main() -> int:
    args = parse_args()
    if not args.accept_research_only:
        raise SystemExit(
            "Treino bloqueado: confirme finalidade experimental com "
            "--accept-research-only."
        )
    taxonomy = load_tissue_taxonomy(args.taxonomy)
    if not taxonomy.clinically_validated:
        raise SystemExit(
            "Treino bloqueado: a taxonomia ainda requer validação clínica."
        )

    audit_config = DatasetAuditConfig(
        dataset_root=args.dataset_root,
        manifest_path=args.manifest,
    )
    audit_report = audit_segmentation_dataset(audit_config, taxonomy)
    if audit_report["release_blockers"]:
        raise SystemExit(
            "Treino bloqueado pela auditoria: "
            + ", ".join(audit_report["release_blockers"])
        )
    samples, orphan_masks = discover_audit_samples(audit_config)
    if orphan_masks:
        raise SystemExit("Treino bloqueado: há máscaras sem imagens.")
    assignments = _load_fold_assignments(args.fold_assignments)
    if set(assignments) != {sample.sample_id for sample in samples}:
        raise SystemExit(
            "Treino bloqueado: os folds não cobrem exatamente as amostras auditadas."
        )

    for duplicate_group in audit_report["duplicates"]["exact_duplicate_groups"]:
        if len({assignments[sample_id] for sample_id in duplicate_group}) > 1:
            raise SystemExit("Treino bloqueado: duplicata exata cruza folds.")
    for pair in audit_report["duplicates"]["near_duplicate_pairs"]:
        if assignments[pair["left_sample_id"]] != assignments[pair["right_sample_id"]]:
            raise SystemExit(
                "Treino bloqueado: possível duplicata próxima cruza folds."
            )

    validation_samples = [
        sample
        for sample in samples
        if assignments[sample.sample_id] == args.validation_fold
    ]
    training_samples = [
        sample
        for sample in samples
        if assignments[sample.sample_id] != args.validation_fold
    ]
    config = MulticlassBaselineConfig(
        image_size=args.image_size,
        base_channels=args.base_channels,
        batch_size=args.batch_size,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        loss_name=args.loss,
        seed=args.seed,
    )
    try:
        metadata = train_multiclass_baseline(
            training_samples,
            validation_samples,
            taxonomy,
            config,
            output_dir=args.output_dir,
            device_name=args.device,
            resume=args.resume,
        )
    except MulticlassBaselineError as exc:
        raise SystemExit(f"Treino bloqueado: {exc}") from exc
    print(
        json.dumps(
            {
                "status": metadata["status"],
                "epochs_completed": metadata["epochs_completed"],
                "best_validation_macro_dice_without_background": metadata[
                    "best_validation_macro_dice_without_background"
                ],
                "test_set_used": metadata["test_set_used"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
