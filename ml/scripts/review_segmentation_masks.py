"""Review wound image/mask pairs locally without uploading clinical previews."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.segmentation_audit import (  # noqa: E402
    DatasetAuditConfig,
    discover_audit_samples,
)
from src.training.segmentation_review import (  # noqa: E402
    MaskReviewError,
    load_review_image,
    write_review_decisions,
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
    parser.add_argument(
        "--review-csv",
        type=Path,
        default=PROJECT_ROOT / "ml" / "outputs" / "mask_review" / "review_status.csv",
    )
    parser.add_argument("--contact-sheet", type=Path)
    parser.add_argument("--max-samples", type=int, default=20)
    parser.add_argument("--alpha", type=float, default=0.45)
    parser.add_argument(
        "--allow-local-clinical-previews",
        action="store_true",
        help="Required acknowledgement: previews stay on the authorized local device.",
    )
    return parser.parse_args()


def _render_triplet(review_image, axes, title: str) -> None:
    axes[0].imshow(review_image.image_rgb)
    axes[0].set_title("Imagem original")
    axes[1].imshow(review_image.color_mask_rgb)
    axes[1].set_title("Máscara indexada")
    axes[2].imshow(review_image.overlay_rgb)
    axes[2].set_title("Overlay")
    for axis in axes:
        axis.axis("off")
    axes[0].set_ylabel(title, fontsize=8)


def _write_contact_sheet(review_images, path: Path) -> None:
    rows = len(review_images)
    figure, axes = plt.subplots(
        rows,
        3,
        figsize=(12, max(3.5 * rows, 4)),
        squeeze=False,
    )
    for row, review_image in enumerate(review_images):
        _render_triplet(review_image, axes[row], review_image.sample_id)
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=140)
    plt.close(figure)


def _interactive_review(review_images, output_path: Path) -> None:
    decisions: dict[str, dict[str, str]] = {}
    state = {"index": 0}
    figure, axes = plt.subplots(1, 3, figsize=(14, 6))

    def draw() -> None:
        for axis in axes:
            axis.clear()
        review_image = review_images[state["index"]]
        current = decisions.get(review_image.sample_id, {})
        status = current.get("review_status", "pendente")
        title = (
            f"{review_image.sample_id} | {state['index'] + 1}/{len(review_images)} "
            f"| status={status} | ←/→ navegar, A aprovar, R revisar, I inválida, Q sair"
        )
        _render_triplet(review_image, axes, title)
        figure.suptitle(title)
        figure.canvas.draw_idle()

    def record(status: str, reason: str = "") -> None:
        review_image = review_images[state["index"]]
        decisions[review_image.sample_id] = {
            "sample_id": review_image.sample_id,
            "review_status": status,
            "reason_code": reason,
        }
        write_review_decisions(output_path, decisions.values())

    def on_key(event) -> None:
        if event.key in {"right", "n"}:
            state["index"] = min(state["index"] + 1, len(review_images) - 1)
        elif event.key in {"left", "p"}:
            state["index"] = max(state["index"] - 1, 0)
        elif event.key == "a":
            record("approved")
        elif event.key == "r":
            record("requires_review", "annotation_disagreement")
        elif event.key == "i":
            record("invalid", "invalid_image_or_mask")
        elif event.key in {"q", "escape"}:
            plt.close(figure)
            return
        draw()

    figure.canvas.mpl_connect("key_press_event", on_key)
    draw()
    plt.show()


def main() -> int:
    args = parse_args()
    if not args.allow_local_clinical_previews:
        raise SystemExit(
            "Visualização bloqueada. Confirme ambiente autorizado com "
            "--allow-local-clinical-previews; nenhuma imagem será enviada."
        )
    if args.max_samples <= 0:
        raise SystemExit("--max-samples deve ser positivo.")

    taxonomy = load_tissue_taxonomy(args.taxonomy)
    samples, _ = discover_audit_samples(
        DatasetAuditConfig(
            dataset_root=args.dataset_root,
            image_dir=args.image_dir,
            mask_dir=args.mask_dir,
            manifest_path=args.manifest,
        )
    )
    review_images = []
    failures = 0
    for sample in samples[: args.max_samples]:
        try:
            review_images.append(
                load_review_image(sample, taxonomy, alpha=args.alpha)
            )
        except MaskReviewError:
            failures += 1

    if not review_images:
        raise SystemExit("Nenhum par válido foi encontrado para revisão.")
    if args.contact_sheet:
        _write_contact_sheet(review_images, args.contact_sheet)
    else:
        _interactive_review(review_images, args.review_csv)

    print(
        f"Revisão local preparada: {len(review_images)} pares; "
        f"{failures} pares inválidos omitidos."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
