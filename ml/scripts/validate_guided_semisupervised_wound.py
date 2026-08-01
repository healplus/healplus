"""Retrain with a frozen holdout and report independent Dice and IoU."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.binary_wound_validation import (  # noqa: E402
    BinaryWoundValidationError,
    clone_validation_workspace,
    evaluate_binary_checkpoint,
    stratified_image_holdout,
)
from src.training.guided_wound_annotation import GuidedAnnotationError  # noqa: E402
from src.training.semi_supervised_wound import (  # noqa: E402
    SemiSupervisedWoundConfig,
    SemiSupervisedWoundError,
    generate_pseudo_labels,
    human_training_samples,
    pseudo_training_samples,
    train_binary_stage,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-workspace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--validation-fraction", type=float, default=0.20)
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--base-channels", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--pseudo-label-weight", type=float, default=0.30)
    parser.add_argument("--foreground-threshold", type=float, default=0.90)
    parser.add_argument("--background-threshold", type=float, default=0.10)
    parser.add_argument(
        "--minimum-confident-pixel-ratio",
        type=float,
        default=0.70,
    )
    parser.add_argument("--decision-threshold", type=float, default=0.50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--confirm-authorized-data", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.confirm_authorized_data:
        raise SystemExit("Validação bloqueada sem --confirm-authorized-data.")
    if args.output.exists():
        allowed_log_files = {
            "validation_stdout.log",
            "validation_stderr.log",
        }
        unexpected_entries = [path for path in args.output.iterdir() if path.name not in allowed_log_files]
        if unexpected_entries:
            raise SystemExit("A pasta de saída da validação já contém artefatos.")
    try:
        workspace = clone_validation_workspace(
            args.source_workspace,
            args.output / "workspace",
        )
        split = stratified_image_holdout(
            workspace,
            validation_fraction=args.validation_fraction,
            seed=args.seed,
        )
        split_path = args.output / "holdout_split.json"
        split_path.parent.mkdir(parents=True, exist_ok=True)
        split_path.write_text(
            json.dumps(split, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        validation_ids = {row["sample_id"] for row in split["assignments"] if row["role"] == "validation"}
        human_samples = human_training_samples(workspace)
        train_human_samples = [sample for sample in human_samples if sample.sample_id not in validation_ids]
        config = SemiSupervisedWoundConfig(
            minimum_human_masks=len(train_human_samples),
            image_size=args.image_size,
            base_channels=args.base_channels,
            batch_size=args.batch_size,
            teacher_epochs=args.epochs,
            student_epochs=args.epochs,
            learning_rate=args.learning_rate,
            pseudo_label_weight=args.pseudo_label_weight,
            foreground_threshold=args.foreground_threshold,
            background_threshold=args.background_threshold,
            minimum_confident_pixel_ratio=args.minimum_confident_pixel_ratio,
            seed=args.seed,
        )
        supervised_path = args.output / "checkpoints" / "supervised_holdout_last.pt"
        supervised = train_binary_stage(
            train_human_samples,
            config,
            output_path=supervised_path,
            stage="teacher",
            epochs=args.epochs,
            device_name=args.device,
            initial_checkpoint=None,
        )
        supervised_metrics = evaluate_binary_checkpoint(
            workspace,
            validation_ids,
            supervised_path,
            args.output / "supervised_validation",
            threshold=args.decision_threshold,
            device_name=args.device,
            seed=args.seed,
        )
        pseudo = generate_pseudo_labels(
            workspace,
            supervised_path,
            config,
            device_name=args.device,
        )
        pseudo_samples = pseudo_training_samples(
            workspace,
            pseudo_label_weight=config.pseudo_label_weight,
        )
        semi_supervised = None
        semi_metrics = None
        if pseudo_samples:
            semi_path = args.output / "checkpoints" / "semi_supervised_holdout_last.pt"
            semi_supervised = train_binary_stage(
                [*train_human_samples, *pseudo_samples],
                config,
                output_path=semi_path,
                stage="student",
                epochs=args.epochs,
                device_name=args.device,
                initial_checkpoint=supervised_path,
            )
            semi_metrics = evaluate_binary_checkpoint(
                workspace,
                validation_ids,
                semi_path,
                args.output / "semi_supervised_validation",
                threshold=args.decision_threshold,
                device_name=args.device,
                seed=args.seed,
            )
        report = {
            "schema_version": "1.0",
            "status": "image_level_holdout_validation_complete",
            "split": split,
            "train_human_masks": len(train_human_samples),
            "validation_human_masks": len(validation_ids),
            "supervised_training": supervised,
            "supervised_validation": supervised_metrics,
            "pseudo_labels": pseudo,
            "semi_supervised_training": semi_supervised,
            "semi_supervised_validation": semi_metrics,
            "governance": {
                "trained_from_random_initialization": True,
                "previous_full_data_checkpoints_loaded": False,
                "validation_masks_used_for_training": False,
                "patient_level_split_possible": False,
                "clinical_use_allowed": False,
                "professional_review_required": True,
            },
        }
        report_path = args.output / "validation_report.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except (
        BinaryWoundValidationError,
        GuidedAnnotationError,
        SemiSupervisedWoundError,
    ) as exc:
        raise SystemExit(f"Validação interrompida com segurança: {exc}") from exc

    final_metrics = semi_metrics or supervised_metrics
    print(
        json.dumps(
            {
                "status": "validation_complete",
                "train_human_masks": len(train_human_samples),
                "validation_human_masks": len(validation_ids),
                "accepted_pseudo_labels": pseudo["accepted_pseudo_labels"],
                "macro_dice": final_metrics["overall"]["macro_dice"],
                "macro_iou": final_metrics["overall"]["macro_iou"],
                "micro_dice": final_metrics["overall"]["micro_dice"],
                "micro_iou": final_metrics["overall"]["micro_iou"],
                "report": str(report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
