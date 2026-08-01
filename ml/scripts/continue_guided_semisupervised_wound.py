"""Continue an existing workspace after a conservative teacher rejects all pseudo-labels."""

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
    GuidedAnnotationApp,
    GuidedAnnotationError,
)
from src.training.semi_supervised_wound import (  # noqa: E402
    SemiSupervisedWoundConfig,
    SemiSupervisedWoundError,
    generate_pseudo_labels,
    generate_human_review_suggestions,
    human_training_samples,
    pseudo_training_samples,
    train_binary_stage,
    write_augmentation_preview,
    write_pipeline_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--review-count", type=int, default=20)
    parser.add_argument("--student-epochs", type=int, default=15)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--base-channels", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--confirm-authorized-data", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.confirm_authorized_data:
        raise SystemExit("Continuação bloqueada sem --confirm-authorized-data.")
    try:
        workspace = AnnotationWorkspace.from_existing(args.workspace)
    except GuidedAnnotationError as exc:
        raise SystemExit(f"Workspace inválido: {exc}") from exc
    initial_human_count = workspace.approved_count
    if initial_human_count < 1:
        raise SystemExit("O workspace não contém máscaras humanas aprovadas.")
    teacher_path = workspace.workspace_root / "checkpoints" / "teacher_last.pt"
    if not teacher_path.is_file():
        raise SystemExit("Checkpoint do professor não encontrado.")

    config = SemiSupervisedWoundConfig(
        minimum_human_masks=initial_human_count,
        image_size=args.image_size,
        base_channels=args.base_channels,
        batch_size=args.batch_size,
        student_epochs=args.student_epochs,
        learning_rate=args.learning_rate,
        seed=args.seed,
    )
    try:
        suggestions = generate_human_review_suggestions(
            workspace,
            teacher_path,
            config,
            count=args.review_count,
            device_name=args.device,
        )
        review_target = min(
            len(workspace.items),
            initial_human_count + suggestions["suggestions"],
        )
        if review_target > initial_human_count:
            app = GuidedAnnotationApp(
                workspace,
                target_approved=review_target,
                prefer_pseudo_suggestions=True,
            )
            app.run()
        if workspace.approved_count < review_target:
            print(
                json.dumps(
                    {
                        "status": "review_incomplete",
                        "approved": workspace.approved_count,
                        "target": review_target,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        human_samples = human_training_samples(workspace)
        bootstrap_student_path = workspace.workspace_root / "checkpoints" / "student_last.pt"
        bootstrap_student = train_binary_stage(
            human_samples,
            config,
            output_path=bootstrap_student_path,
            stage="student",
            epochs=config.student_epochs,
            device_name=args.device,
            initial_checkpoint=teacher_path,
        )
        pseudo_summary = generate_pseudo_labels(
            workspace,
            bootstrap_student_path,
            config,
            device_name=args.device,
        )
        pseudo_samples = pseudo_training_samples(
            workspace,
            pseudo_label_weight=config.pseudo_label_weight,
        )
        student = bootstrap_student
        if pseudo_samples:
            semi_supervised_path = workspace.workspace_root / "checkpoints" / "semi_supervised_student_last.pt"
            student = train_binary_stage(
                [*human_samples, *pseudo_samples],
                config,
                output_path=semi_supervised_path,
                stage="student",
                epochs=config.student_epochs,
                device_name=args.device,
                initial_checkpoint=bootstrap_student_path,
            )
        teacher_checkpoint = torch.load(
            teacher_path,
            map_location="cpu",
            weights_only=False,
        )
        teacher = {
            "checkpoint": str(teacher_path),
            "stage": "teacher",
            "epochs": int(teacher_checkpoint["epoch"]) + 1,
            "human_samples": int(teacher_checkpoint["human_samples"]),
            "pseudo_samples": 0,
            "validation_used": False,
            "test_set_used": False,
        }
        pseudo_summary["review_only_fallback"] = suggestions
        pseudo_summary["bootstrap_student"] = bootstrap_student
        preview = workspace.workspace_root / "augmentation_preview_20.png"
        if not preview.is_file():
            preview = write_augmentation_preview(
                workspace,
                count=20,
                seed=config.seed,
            )
        report = write_pipeline_report(
            workspace,
            config,
            teacher_result=teacher,
            pseudo_result=pseudo_summary,
            student_result=student,
            augmentation_preview=preview,
        )
    except (GuidedAnnotationError, SemiSupervisedWoundError) as exc:
        raise SystemExit(f"Continuação interrompida com segurança: {exc}") from exc

    print(
        json.dumps(
            {
                "status": "human_reviewed_student_complete",
                "approved_human_masks": workspace.approved_count,
                "review_only_suggestions": suggestions["suggestions"],
                "accepted_pseudo_labels": pseudo_summary["accepted_pseudo_labels"],
                "pseudo_masks_used_with_reduced_weight": len(pseudo_samples),
                "student_checkpoint": student["checkpoint"],
                "report": str(report),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
