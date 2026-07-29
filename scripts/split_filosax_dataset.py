"""Build a leakage-safe, deterministic train/validation/test split plan from a Filosax manifest.

Reads a manifest produced by scripts/prepare_filosax_dataset.py. Groups files
by their top-level directory (one prepared piece/session per group) so no
piece's audio or annotations ever spans more than one split. This tool does
not touch the raw dataset itself, only the manifest describing it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from saxo_ai.domain.dataset_splits import DatasetSplitPlan

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

DEFAULT_TRAIN = 0.7
DEFAULT_VALIDATION = 0.15
DEFAULT_TEST = 0.15
DEFAULT_SEED = "saxo-ai-filosax-split-v1"


def _ensure_source_path() -> None:
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))


def build_plan(
    *,
    manifest_path: Path,
    train: float,
    validation: float,
    test: float,
    seed: str,
) -> DatasetSplitPlan:
    _ensure_source_path()
    from saxo_ai.application.dataset_split_planning import (
        AssignDatasetSplits,
        top_level_directory_group_key,
    )
    from saxo_ai.domain.dataset_splits import DatasetSplitProportions
    from saxo_ai.infrastructure.dataset_manifest_fs import load_dataset_manifest_json

    manifest = load_dataset_manifest_json(manifest_path)
    proportions = DatasetSplitProportions(train=train, validation=validation, test=test)
    use_case = AssignDatasetSplits(proportions=proportions, seed=seed)
    return use_case.execute(manifest, group_key=top_level_directory_group_key)


def run(
    *,
    manifest_path: Path,
    output: Path,
    train: float,
    validation: float,
    test: float,
    seed: str,
) -> int:
    _ensure_source_path()
    from saxo_ai.domain.dataset_splits import DatasetSplitName
    from saxo_ai.infrastructure.dataset_split_plan_json import write_dataset_split_plan_json

    plan = build_plan(
        manifest_path=manifest_path, train=train, validation=validation, test=test, seed=seed
    )
    write_dataset_split_plan_json(plan, output)
    for split in DatasetSplitName:
        print(
            f"{split.value}: {plan.group_count_for(split)} groups, "
            f"{len(plan.paths_for(split))} files"
        )
    print(f"Wrote split plan to {output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--train", type=float, default=DEFAULT_TRAIN)
    parser.add_argument("--validation", type=float, default=DEFAULT_VALIDATION)
    parser.add_argument("--test", type=float, default=DEFAULT_TEST)
    parser.add_argument("--seed", type=str, default=DEFAULT_SEED)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run(
        manifest_path=args.manifest,
        output=args.output,
        train=args.train,
        validation=args.validation,
        test=args.test,
        seed=args.seed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
