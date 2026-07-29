from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "prepare_filosax_dataset.py"
REGISTRY_PATH = ROOT / "dataset-registry" / "registry-v1.json"


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("prepare_filosax_dataset", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare_filosax_dataset = _load_script_module()


def write_synthetic_raw_files(root: Path) -> None:
    (root / "P1").mkdir(parents=True)
    (root / "P1" / "take1.wav").write_bytes(b"synthetic-audio-one")
    (root / "Bass_Drums.wav").write_bytes(b"synthetic-audio-two")


class TestPrepareFilosaxDatasetCli:
    def test_manifest_then_verify_round_trip(self, tmp_path: Path) -> None:
        raw_root = tmp_path / "raw"
        write_synthetic_raw_files(raw_root)
        manifest_path = tmp_path / "manifest.json"

        manifest_exit_code = prepare_filosax_dataset.main(
            ["manifest", str(raw_root), str(manifest_path)]
        )
        assert manifest_exit_code == 0
        assert manifest_path.exists()
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert payload["dataset_id"] == "filosax"

        verify_exit_code = prepare_filosax_dataset.main(
            ["verify", str(raw_root), str(manifest_path)]
        )
        assert verify_exit_code == 0

    def test_verify_detects_drift(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        raw_root = tmp_path / "raw"
        write_synthetic_raw_files(raw_root)
        manifest_path = tmp_path / "manifest.json"
        prepare_filosax_dataset.main(["manifest", str(raw_root), str(manifest_path)])

        (raw_root / "Bass_Drums.wav").write_bytes(b"mutated-content")

        exit_code = prepare_filosax_dataset.main(["verify", str(raw_root), str(manifest_path)])

        assert exit_code == 1
        assert "MISMATCHED: Bass_Drums.wav" in capsys.readouterr().err

    def test_rejects_unregistered_dataset_id(self, tmp_path: Path) -> None:
        raw_root = tmp_path / "raw"
        write_synthetic_raw_files(raw_root)
        empty_registry = tmp_path / "empty-registry.json"
        empty_registry.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "datasets": [
                        {
                            "dataset_id": "other-dataset",
                            "title": "Other",
                            "creators": ["Someone"],
                            "publisher": "Someone",
                            "release_reference": "ref",
                            "canonical_uri": "https://example.org/records/1",
                            "doi": "10.1234/example.1",
                            "access_mode": "open",
                            "license": {
                                "kind": "spdx",
                                "identifier": "MIT",
                                "title": "MIT",
                                "terms_uri": "https://example.org/mit",
                                "attribution_required": False,
                                "required_citation": "",
                                "terms_may_change": False,
                            },
                            "use_rules": [
                                {"use": use, "decision": "allowed", "conditions": []}
                                for use in (
                                    "download",
                                    "internal_noncommercial_research",
                                    "commercial_use",
                                    "redistribution",
                                    "reproduction_material_distribution",
                                    "publication_of_results",
                                    "derived_asset_distribution",
                                )
                            ],
                            "evidence": [
                                {
                                    "kind": "official_documentation",
                                    "uri": "https://example.org/docs",
                                    "reviewed_on": "2026-07-01",
                                }
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(SystemExit):
            prepare_filosax_dataset.main(
                [
                    "--registry",
                    str(empty_registry),
                    "manifest",
                    str(raw_root),
                    str(tmp_path / "manifest.json"),
                ]
            )

    def test_default_registry_already_has_filosax_registered(self) -> None:
        assert REGISTRY_PATH.exists()
        payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        assert any(dataset["dataset_id"] == "filosax" for dataset in payload["datasets"])
