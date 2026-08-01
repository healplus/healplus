"""Combine reviewed wound workspaces and source groups without raw path leakage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.guided_workspace_merge import (  # noqa: E402
    build_combined_workspace,
)
from src.training.guided_wound_annotation import GuidedAnnotationError  # noqa: E402


def _image_group(value: str) -> tuple[str, Path]:
    label, separator, raw_path = value.partition("=")
    if not separator or not label.strip() or not raw_path.strip():
        raise argparse.ArgumentTypeError("use LABEL=PATH for --image-group")
    return label.strip(), Path(raw_path.strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--image-group",
        action="append",
        required=True,
        type=_image_group,
        help="Grupo e pasta no formato LABEL=PATH; pode ser repetido.",
    )
    parser.add_argument(
        "--reviewed-workspace",
        action="append",
        required=True,
        type=Path,
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--confirm-authorized-data", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.confirm_authorized_data:
        raise SystemExit("Combinação bloqueada sem --confirm-authorized-data.")
    image_groups = dict(args.image_group)
    if len(image_groups) != len(args.image_group):
        raise SystemExit("Os rótulos de --image-group devem ser únicos.")
    try:
        result = build_combined_workspace(
            image_groups,
            args.reviewed_workspace,
            args.output,
        )
    except GuidedAnnotationError as exc:
        raise SystemExit(f"Combinação interrompida com segurança: {exc}") from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
