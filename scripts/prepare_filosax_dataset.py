"""Build and verify a reproducible manifest for a locally, legally obtained Filosax copy.

This tool never downloads, stores, or redistributes Filosax content. It only
hashes files the operator has already placed on disk under their own,
separately obtained access to the restricted dataset (see
docs/contracts/filosax-dataset-preparation-v1.md).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from saxo_ai.domain.dataset_manifest import DatasetManifest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DATASET_ID = "filosax"
DEFAULT_REGISTRY_PATH = ROOT / "dataset-registry" / "registry-v1.json"


def _ensure_source_path() -> None:
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))


def _require_registered_dataset(registry_path: Path) -> None:
    _ensure_source_path()
    from saxo_ai.infrastructure.dataset_registry_json import load_dataset_registry

    registry = load_dataset_registry(registry_path)
    dataset_ids = {dataset.dataset_id for dataset in registry.datasets}
    if DATASET_ID not in dataset_ids:
        raise SystemExit(
            f"'{DATASET_ID}' is not registered in {registry_path}. "
            "Governance must be recorded before preparing the dataset."
        )


def _build_manifest(raw_root: Path) -> DatasetManifest:
    _ensure_source_path()
    from saxo_ai.infrastructure.dataset_manifest_fs import build_dataset_manifest_from_directory

    return build_dataset_manifest_from_directory(raw_root, DATASET_ID)


def run_manifest(*, raw_root: Path, output: Path, registry_path: Path) -> int:
    _require_registered_dataset(registry_path)
    _ensure_source_path()
    from saxo_ai.infrastructure.dataset_manifest_fs import write_dataset_manifest_json

    manifest = _build_manifest(raw_root)
    write_dataset_manifest_json(manifest, output)
    print(f"Wrote manifest for {len(manifest.files)} files to {output}")
    return 0


def run_verify(*, raw_root: Path, manifest_path: Path, registry_path: Path) -> int:
    _require_registered_dataset(registry_path)
    _ensure_source_path()
    from saxo_ai.domain.dataset_manifest import compare_dataset_manifests
    from saxo_ai.infrastructure.dataset_manifest_fs import load_dataset_manifest_json

    expected = load_dataset_manifest_json(manifest_path)
    actual = _build_manifest(raw_root)
    comparison = compare_dataset_manifests(expected, actual)
    if comparison.is_reproducible:
        print(f"Reproducible: {len(actual.files)} files match {manifest_path}")
        return 0

    for path in comparison.missing_paths:
        print(f"MISSING: {path}", file=sys.stderr)
    for path in comparison.unexpected_paths:
        print(f"UNEXPECTED: {path}", file=sys.stderr)
    for path in comparison.mismatched_paths:
        print(f"MISMATCHED: {path}", file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest_parser = subparsers.add_parser(
        "manifest", help="Hash a local raw Filosax copy into a reproducible manifest."
    )
    manifest_parser.add_argument("raw_root", type=Path)
    manifest_parser.add_argument("output", type=Path)

    verify_parser = subparsers.add_parser(
        "verify", help="Re-hash a local raw Filosax copy and compare it to a captured manifest."
    )
    verify_parser.add_argument("raw_root", type=Path)
    verify_parser.add_argument("manifest", type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "manifest":
        return run_manifest(raw_root=args.raw_root, output=args.output, registry_path=args.registry)
    return run_verify(
        raw_root=args.raw_root, manifest_path=args.manifest, registry_path=args.registry
    )


if __name__ == "__main__":
    raise SystemExit(main())
