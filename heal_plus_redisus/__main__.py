"""Run the explicitly synthetic, offline end-to-end demonstration."""

import argparse
from datetime import datetime
import json
from pathlib import Path

from .examples.synthetic_demo import run_demo


def main():
    parser = argparse.ArgumentParser(
        description="HEAL+ Sprints 1 e 2: demonstração sintética sem pesos ou dados reais."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/generated") / ("heal-sprints-" + datetime.now().strftime("%Y%m%d-%H%M%S")),
        help="Nova pasta para evidências sintéticas; não sobrescreve uma execução anterior.",
    )
    args = parser.parse_args()
    print(json.dumps(run_demo(args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
