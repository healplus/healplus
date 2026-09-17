"""Train and test a four-level transfer-learning segmentation experiment."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.binary_wound_validation import (  # noqa: E402
    BinaryWoundValidationError,
    clone_validation_workspace,
    stratified_train_validation_test_split,
)
from src.training.guided_wound_annotation import GuidedAnnotationError  # noqa: E402
from src.training.semi_supervised_wound import (  # noqa: E402
    BinaryTrainingSample,
    SemiSupervisedWoundConfig,
    SemiSupervisedWoundError,
    human_training_samples,
    pseudo_training_samples,
)
from src.training.transfer_wound_segmentation import (  # noqa: E402
    TransferWoundSegmentationError,
    calibrate_decision_threshold,
    evaluate_lraspp_checkpoint,
    generate_lraspp_pseudo_labels,
    train_lraspp_stage,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-workspace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--validation-fraction", type=float, default=0.15)
    parser.add_argument("--test-fraction", type=float, default=0.15)
    parser.add_argument("--teacher-epochs", type=int, default=30)
    parser.add_argument("--student-epochs", type=int, default=20)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=5e-4)
    parser.add_argument(
        "--pretraining",
        choices=["imagenet", "coco_segmentation"],
        default="imagenet",
    )
    parser.add_argument(
        "--positive-weight-strategy",
        choices=["ratio", "sqrt_ratio", "none"],
        default="sqrt_ratio",
    )
    parser.add_argument("--pseudo-label-weight", type=float, default=0.30)
    parser.add_argument("--foreground-threshold", type=float, default=0.90)
    parser.add_argument("--background-threshold", type=float, default=0.10)
    parser.add_argument(
        "--minimum-confident-pixel-ratio",
        type=float,
        default=0.70,
    )
    parser.add_argument("--maximum-pseudo-samples", type=int, default=400)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--confirm-authorized-data", action="store_true")
    return parser.parse_args()


def _select_balanced_pseudo_samples(
    workspace,
    samples: list[BinaryTrainingSample],
    *,
    maximum: int,
) -> list[BinaryTrainingSample]:
    if len(samples) <= maximum:
        return samples
    grouped: dict[str, list[BinaryTrainingSample]] = defaultdict(list)
    for sample in samples:
        groups = workspace.record(sample.sample_id).get(
            "source_groups",
            ["unknown"],
        )
        grouped[str(groups[0] if groups else "unknown")].append(sample)
    for group_samples in grouped.values():
        group_samples.sort(
            key=lambda sample: float(
                workspace.record(sample.sample_id).get(
                    "pseudo_confidence",
                    0.0,
                )
            ),
            reverse=True,
        )
    group_limit = max(1, maximum // len(grouped))
    selected = [sample for group in sorted(grouped) for sample in grouped[group][:group_limit]]
    if len(selected) < maximum:
        selected_ids = {sample.sample_id for sample in selected}
        remaining = [sample for sample in samples if sample.sample_id not in selected_ids]
        remaining.sort(
            key=lambda sample: float(
                workspace.record(sample.sample_id).get(
                    "pseudo_confidence",
                    0.0,
                )
            ),
            reverse=True,
        )
        selected.extend(remaining[: maximum - len(selected)])
    return selected[:maximum]


def _technical_gate(metrics: dict) -> dict:
    overall = metrics["overall"]
    group_dice = {group: values["macro_dice"] for group, values in metrics["by_source_group"].items()}
    checks = {
        "macro_dice_at_least_0_80": overall["macro_dice"] >= 0.80,
        "macro_iou_at_least_0_67": overall["macro_iou"] >= 0.67,
        "precision_at_least_0_80": overall["precision"] >= 0.80,
        "recall_at_least_0_80": overall["recall"] >= 0.80,
        "dice_ci_lower_at_least_0_75": (overall["dice_95_ci"]["lower_95"] >= 0.75),
        "every_source_group_dice_at_least_0_75": (bool(group_dice) and min(group_dice.values()) >= 0.75),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "note": (
            "This internal engineering gate cannot establish clinical "
            "adequacy without patient-grouped external and prospective "
            "validation."
        ),
    }


def main() -> int:
    args = parse_args()
    if not args.confirm_authorized_data:
        raise SystemExit("Experimento bloqueado sem --confirm-authorized-data.")
    if args.maximum_pseudo_samples < 1:
        raise SystemExit("--maximum-pseudo-samples deve ser positivo.")
    if args.output.exists():
        allowed_logs = {
            "four_level_stdout.log",
            "four_level_stderr.log",
        }
        unexpected = [path for path in args.output.iterdir() if path.name not in allowed_logs]
        if unexpected:
            raise SystemExit("A pasta de saída já contém artefatos do experimento.")
    try:
        workspace = clone_validation_workspace(
            args.source_workspace,
            args.output / "workspace",
        )
        split = stratified_train_validation_test_split(
            workspace,
            validation_fraction=args.validation_fraction,
            test_fraction=args.test_fraction,
            seed=args.seed,
        )
        split_path = args.output / "train_validation_test_split.json"
        split_path.parent.mkdir(parents=True, exist_ok=True)
        split_path.write_text(
            json.dumps(split, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        role_ids = {
            role: {row["sample_id"] for row in split["assignments"] if row["role"] == role}
            for role in ("train", "validation", "test")
        }
        all_human = human_training_samples(workspace)
        train_human = [sample for sample in all_human if sample.sample_id in role_ids["train"]]
        validation_human = [sample for sample in all_human if sample.sample_id in role_ids["validation"]]
        config = SemiSupervisedWoundConfig(
            minimum_human_masks=len(train_human),
            image_size=args.image_size,
            base_channels=16,
            batch_size=args.batch_size,
            teacher_epochs=args.teacher_epochs,
            student_epochs=args.student_epochs,
            learning_rate=args.learning_rate,
            pseudo_label_weight=args.pseudo_label_weight,
            foreground_threshold=args.foreground_threshold,
            background_threshold=args.background_threshold,
            minimum_confident_pixel_ratio=args.minimum_confident_pixel_ratio,
            seed=args.seed,
        )
        teacher_path = args.output / "checkpoints" / "lraspp_teacher_best.pt"
        teacher = train_lraspp_stage(
            train_human,
            validation_human,
            config,
            output_path=teacher_path,
            stage="teacher",
            epochs=args.teacher_epochs,
            device_name=args.device,
            pretraining=args.pretraining,
            positive_weight_strategy=args.positive_weight_strategy,
        )
        teacher_calibration = calibrate_decision_threshold(
            workspace,
            role_ids["validation"],
            teacher_path,
            device_name=args.device,
        )
        teacher_test = evaluate_lraspp_checkpoint(
            workspace,
            role_ids["test"],
            teacher_path,
            args.output / "teacher_test",
            role="test",
            device_name=args.device,
            seed=args.seed,
        )
        pseudo_summary = generate_lraspp_pseudo_labels(
            workspace,
            teacher_path,
            config,
            device_name=args.device,
        )
        all_pseudo_samples = pseudo_training_samples(
            workspace,
            pseudo_label_weight=config.pseudo_label_weight,
        )
        selected_pseudo = _select_balanced_pseudo_samples(
            workspace,
            all_pseudo_samples,
            maximum=args.maximum_pseudo_samples,
        )
        student = None
        student_calibration = None
        student_test = None
        if selected_pseudo:
            student_path = args.output / "checkpoints" / "lraspp_student_best.pt"
            student = train_lraspp_stage(
                [*train_human, *selected_pseudo],
                validation_human,
                config,
                output_path=student_path,
                stage="student",
                epochs=args.student_epochs,
                device_name=args.device,
                initial_checkpoint=teacher_path,
                pretraining=args.pretraining,
                positive_weight_strategy=args.positive_weight_strategy,
            )
            student_calibration = calibrate_decision_threshold(
                workspace,
                role_ids["validation"],
                student_path,
                device_name=args.device,
            )
            student_test = evaluate_lraspp_checkpoint(
                workspace,
                role_ids["test"],
                student_path,
                args.output / "student_test",
                role="test",
                device_name=args.device,
                seed=args.seed,
            )
        final_metrics = student_test or teacher_test
        technical_gate = _technical_gate(final_metrics)
        report = {
            "schema_version": "1.0",
            "status": "four_level_transfer_experiment_complete",
            "architecture": "LR-ASPP MobileNetV3 Large",
            "pretraining": args.pretraining,
            "positive_weight_strategy": args.positive_weight_strategy,
            "split": split,
            "train_human_masks": len(train_human),
            "validation_human_masks": len(role_ids["validation"]),
            "test_human_masks": len(role_ids["test"]),
            "augmentation": {
                "training_only": True,
                "horizontal_flip": True,
                "rotation_degrees": 15,
                "brightness_contrast": True,
                "saturation": True,
                "vertical_flip": False,
            },
            "teacher": teacher,
            "teacher_threshold_calibration": teacher_calibration,
            "teacher_test": teacher_test,
            "pseudo_labels": pseudo_summary,
            "pseudo_samples_selected_for_student": len(selected_pseudo),
            "student": student,
            "student_threshold_calibration": student_calibration,
            "student_test": student_test,
            "technical_gate": technical_gate,
            "clinical_readiness": {
                "adequate_for_clinical_use": False,
                "reason": (
                    "Clinical adequacy requires patient-grouped external and "
                    "prospective validation, clinical workflow testing and "
                    "applicable regulatory review."
                ),
            },
            "governance": {
                "test_role_used_during_training": False,
                "test_role_used_for_threshold_selection": False,
                "patient_level_split_possible": False,
                "stage_3_and_4_human_ground_truth_available": False,
                "stage_3_and_4_used_only_as_unlabeled_data": True,
                "clinical_use_allowed": False,
            },
        }
        report_path = args.output / "four_level_experiment_report.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except (
        BinaryWoundValidationError,
        GuidedAnnotationError,
        SemiSupervisedWoundError,
        TransferWoundSegmentationError,
    ) as exc:
        raise SystemExit(f"Experimento interrompido com segurança: {exc}") from exc

    print(
        json.dumps(
            {
                "status": "four_level_experiment_complete",
                "architecture": report["architecture"],
                "pseudo_labels_accepted": pseudo_summary["accepted_pseudo_labels"],
                "pseudo_samples_used": len(selected_pseudo),
                "test_macro_dice": final_metrics["overall"]["macro_dice"],
                "test_macro_iou": final_metrics["overall"]["macro_iou"],
                "technical_gate_passed": technical_gate["passed"],
                "clinical_use_allowed": False,
                "report": str(report_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
