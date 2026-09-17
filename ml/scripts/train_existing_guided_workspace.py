"""Train an existing reviewed workspace, then use only gated pseudo-labels."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.guided_wound_annotation import (  # noqa: E402
    AnnotationWorkspace,
    GuidedAnnotationError,
)
from src.training.semi_supervised_wound import (  # noqa: E402
    SemiSupervisedWoundConfig,
    SemiSupervisedWoundError,
    generate_pseudo_labels,
    human_training_samples,
    pseudo_training_samples,
    train_binary_stage,
    write_augmentation_preview,
    write_pipeline_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--initial-checkpoint", type=Path)
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
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--confirm-authorized-data", action="store_true")
    return parser.parse_args()


def _checkpoint_result(path: Path) -> dict:
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    return {
        "checkpoint": str(path),
        "stage": checkpoint["stage"],
        "epochs": int(checkpoint["epoch"]) + 1,
        "human_samples": int(checkpoint["human_samples"]),
        "pseudo_samples": int(checkpoint["pseudo_samples"]),
        "validation_used": bool(checkpoint.get("validation_used", False)),
        "test_set_used": bool(checkpoint.get("test_set_used", False)),
        "history": checkpoint.get("history", []),
    }


def main() -> int:
    args = parse_args()
    if not args.confirm_authorized_data:
        raise SystemExit("Treinamento bloqueado sem --confirm-authorized-data.")
    if args.initial_checkpoint and not args.initial_checkpoint.is_file():
        raise SystemExit("Checkpoint inicial não encontrado.")
    try:
        workspace = AnnotationWorkspace.from_existing(args.workspace)
        human_samples = human_training_samples(workspace)
        config = SemiSupervisedWoundConfig(
            minimum_human_masks=len(human_samples),
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
        supervised_path = workspace.workspace_root / "checkpoints" / "combined_supervised_last.pt"
        supervised = train_binary_stage(
            human_samples,
            config,
            output_path=supervised_path,
            stage="student",
            epochs=args.epochs,
            device_name=args.device,
            initial_checkpoint=args.initial_checkpoint,
        )
        pseudo_summary = generate_pseudo_labels(
            workspace,
            supervised_path,
            config,
            device_name=args.device,
        )
        pseudo_samples = pseudo_training_samples(
            workspace,
            pseudo_label_weight=config.pseudo_label_weight,
        )
        final_student = supervised
        if pseudo_samples:
            semi_supervised_path = workspace.workspace_root / "checkpoints" / "semi_supervised_student_last.pt"
            final_student = train_binary_stage(
                [*human_samples, *pseudo_samples],
                config,
                output_path=semi_supervised_path,
                stage="student",
                epochs=args.epochs,
                device_name=args.device,
                initial_checkpoint=supervised_path,
            )
        preview = write_augmentation_preview(
            workspace,
            count=20,
            seed=config.seed,
        )
        initial_result = (
            _checkpoint_result(args.initial_checkpoint)
            if args.initial_checkpoint
            else {
                "checkpoint": None,
                "stage": "random_initialization",
                "epochs": 0,
                "human_samples": 0,
                "pseudo_samples": 0,
                "validation_used": False,
                "test_set_used": False,
            }
        )
        pseudo_summary["combined_supervised_stage"] = supervised
        report = write_pipeline_report(
            workspace,
            config,
            teacher_result=initial_result,
            pseudo_result=pseudo_summary,
            student_result=final_student,
            augmentation_preview=preview,
        )
    except (GuidedAnnotationError, SemiSupervisedWoundError) as exc:
        raise SystemExit(f"Treinamento interrompido com segurança: {exc}") from exc

    print(
        json.dumps(
            {
                "status": "training_complete",
                "approved_human_masks": workspace.approved_count,
                "accepted_pseudo_labels": pseudo_summary["accepted_pseudo_labels"],
                "final_checkpoint": final_student["checkpoint"],
                "report": str(report),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
