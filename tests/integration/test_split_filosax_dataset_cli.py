from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
PREPARE_SCRIPT_PATH = ROOT / "scripts" / "prepare_filosax_dataset.py"
SPLIT_SCRIPT_PATH = ROOT / "scripts" / "split_filosax_dataset.py"


def _load_script_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare_filosax_dataset = _load_script_module(PREPARE_SCRIPT_PATH, "prepare_filosax_dataset")
split_filosax_dataset = _load_script_module(SPLIT_SCRIPT_PATH, "split_filosax_dataset")


def write_synthetic_raw_files(root: Path, piece_count: int) -> None:
    for piece in range(piece_count):
        piece_dir = root / f"piece-{piece:03d}"
        piece_dir.mkdir(parents=True)
        (piece_dir / "Bass_Drums.wav").write_bytes(f"audio-{piece}-a".encode())
        (piece_dir / "P1.wav").write_bytes(f"audio-{piece}-b".encode())


class TestSplitFilosaxDatasetCli:
    def test_builds_a_leakage_safe_plan_from_a_real_manifest(self, tmp_path: Path) -> None:
        raw_root = tmp_path / "raw"
        write_synthetic_raw_files(raw_root, piece_count=30)
        manifest_path = tmp_path / "manifest.json"
        prepare_filosax_dataset.main(["manifest", str(raw_root), str(manifest_path)])

        split_path = tmp_path / "split-plan.json"
        exit_code = split_filosax_dataset.main(
            ["--seed", "cli-test-seed", str(manifest_path), str(split_path)]
        )

        assert exit_code == 0
        payload = json.loads(split_path.read_text(encoding="utf-8"))
        assert payload["dataset_id"] == "filosax"
        assignments = payload["assignments"]
        assert len(assignments) == 60

        splits_by_group: dict[str, set[str]] = {}
        for item in assignments:
            splits_by_group.setdefault(item["group_key"], set()).add(item["split"])
        assert all(len(splits) == 1 for splits in splits_by_group.values())
