"""One-command local wound annotation and semi-supervised training workflow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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
    generate_human_review_suggestions,
    generate_pseudo_labels,
    human_training_samples,
    pseudo_training_samples,
    train_binary_stage,
    write_augmentation_preview,
    write_pipeline_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--images",
        type=Path,
        help="Pasta local autorizada. Se omitida, abre um seletor de pasta.",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=PROJECT_ROOT / "ml" / "outputs" / "guided_wound_workflow",
        help="Pasta local de trabalho; não use uma pasta sincronizada/publicada.",
    )
    parser.add_argument("--target-human", type=int, default=100)
    parser.add_argument("--pseudo-review-count", type=int, default=20)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--base-channels", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--teacher-epochs", type=int, default=15)
    parser.add_argument("--student-epochs", type=int, default=15)
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
    parser.add_argument(
        "--annotation-only",
        action="store_true",
        help="Para após atingir a meta humana, sem iniciar treinamento.",
    )
    parser.add_argument(
        "--skip-pseudo-review",
        action="store_true",
        help="Não abre a segunda rodada assistida; pseudo-rótulos continuam com peso menor.",
    )
    parser.add_argument(
        "--confirm-authorized-data",
        action="store_true",
        help="Confirma consentimento/licença e ambiente local autorizado.",
    )
    return parser.parse_args()


def _choose_image_directory() -> Path:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise SystemExit(
            "Não foi possível abrir o seletor. Informe a pasta com --images."
        ) from exc
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.askdirectory(
        title="Selecione somente a pasta com as imagens de feridas",
        mustexist=True,
    )
    root.destroy()
    if not selected:
        raise SystemExit("Nenhuma pasta de imagens foi selecionada.")
    return Path(selected)


def _progress_payload(workspace, target: int) -> dict[str, int | str]:
    return {
        "status": "annotation_incomplete",
        "approved": workspace.approved_count,
        "target": target,
        "remaining": max(target - workspace.approved_count, 0),
    }


def main() -> int:
    args = parse_args()
    if not args.confirm_authorized_data:
        raise SystemExit(
            "Fluxo bloqueado: confirme que as imagens estão autorizadas para "
            "pesquisa local com --confirm-authorized-data."
        )
    image_root = args.images or _choose_image_directory()
    try:
        workspace = AnnotationWorkspace(image_root, args.workspace)
    except GuidedAnnotationError as exc:
        raise SystemExit(f"Não foi possível iniciar: {exc}") from exc
    if len(workspace.items) < args.target_human:
        raise SystemExit(
            f"Foram encontradas {len(workspace.items)} imagens únicas; "
            f"a meta solicitada é {args.target_human}."
        )

    if workspace.approved_count < args.target_human:
        app = GuidedAnnotationApp(
            workspace,
            target_approved=args.target_human,
        )
        app.run()
    if workspace.approved_count < args.target_human:
        print(
            json.dumps(
                _progress_payload(workspace, args.target_human),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.annotation_only:
        print(
            json.dumps(
                {
                    "status": "human_annotation_target_complete",
                    "approved": workspace.approved_count,
                    "workspace": str(workspace.workspace_root),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    config = SemiSupervisedWoundConfig(
        minimum_human_masks=args.target_human,
        image_size=args.image_size,
        base_channels=args.base_channels,
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
    try:
        config.validate()
        preview = write_augmentation_preview(
            workspace,
            count=20,
            seed=config.seed,
        )
        checkpoint_dir = workspace.workspace_root / "checkpoints"
        teacher_path = checkpoint_dir / "teacher_last.pt"
        teacher_result = train_binary_stage(
            human_training_samples(workspace),
            config,
            output_path=teacher_path,
            stage="teacher",
            epochs=config.teacher_epochs,
            device_name=args.device,
        )
        pseudo_result = generate_pseudo_labels(
            workspace,
            teacher_path,
            config,
            device_name=args.device,
        )
        review_candidates = int(pseudo_result["accepted_pseudo_labels"])
        if review_candidates == 0 and args.pseudo_review_count > 0:
            review_only = generate_human_review_suggestions(
                workspace,
                teacher_path,
                config,
                count=args.pseudo_review_count,
                device_name=args.device,
            )
            pseudo_result["review_only_fallback"] = review_only
            review_candidates = int(review_only["suggestions"])

        if (
            not args.skip_pseudo_review
            and args.pseudo_review_count > 0
            and review_candidates > 0
        ):
            review_target = min(
                len(workspace.items),
                workspace.approved_count + args.pseudo_review_count,
            )
            review_app = GuidedAnnotationApp(
                workspace,
                target_approved=review_target,
                prefer_pseudo_suggestions=True,
            )
            review_app.run()
            if workspace.approved_count < review_target:
                print(
                    json.dumps(
                        {
                            "status": "pseudo_review_incomplete",
                            "approved": workspace.approved_count,
                            "review_target": review_target,
                            "teacher_checkpoint": str(teacher_path),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 0

        pseudo_samples = pseudo_training_samples(
            workspace,
            pseudo_label_weight=config.pseudo_label_weight,
        )
        student_result = None
        if (
            pseudo_samples
            or pseudo_result["accepted_pseudo_labels"] > 0
            or workspace.approved_count > config.minimum_human_masks
        ):
            student_path = checkpoint_dir / "student_last.pt"
            student_result = train_binary_stage(
                [*human_training_samples(workspace), *pseudo_samples],
                config,
                output_path=student_path,
                stage="student",
                epochs=config.student_epochs,
                device_name=args.device,
                initial_checkpoint=teacher_path,
            )
        report_path = write_pipeline_report(
            workspace,
            config,
            teacher_result=teacher_result,
            pseudo_result=pseudo_result,
            student_result=student_result,
            augmentation_preview=preview,
        )
    except (GuidedAnnotationError, SemiSupervisedWoundError) as exc:
        raise SystemExit(f"Pipeline interrompido com segurança: {exc}") from exc

    print(
        json.dumps(
            {
                "status": (
                    "semi_supervised_training_complete"
                    if student_result
                    else "teacher_complete_no_accepted_pseudo_labels"
                ),
                "human_masks": workspace.approved_count,
                "pseudo_masks_used": len(pseudo_samples),
                "teacher_checkpoint": teacher_result["checkpoint"],
                "student_checkpoint": (
                    student_result["checkpoint"] if student_result else None
                ),
                "augmentation_preview": str(preview),
                "report": str(report_path),
                "clinical_status": "experimental_requires_professional_review",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
