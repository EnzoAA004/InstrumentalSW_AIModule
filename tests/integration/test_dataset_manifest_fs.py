from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from saxo_ai.domain.dataset_manifest import InvalidDatasetManifestError
from saxo_ai.infrastructure.dataset_manifest_fs import (
    DatasetDirectoryNotFoundError,
    InvalidDatasetManifestJsonError,
    build_dataset_manifest_from_directory,
    load_dataset_manifest_json,
    write_dataset_manifest_json,
)


def write_synthetic_raw_files(root: Path) -> None:
    (root / "P1").mkdir(parents=True)
    (root / "P1" / "take1.wav").write_bytes(b"synthetic-audio-one")
    (root / "Bass_Drums.wav").write_bytes(b"synthetic-audio-two")
    (root / "annotations").mkdir()
    (root / "annotations" / "take1.jams").write_text("{}", encoding="utf-8")


class TestBuildDatasetManifestFromDirectory:
    def test_hashes_every_file_deterministically(self, tmp_path: Path) -> None:
        raw_root = tmp_path / "raw"
        write_synthetic_raw_files(raw_root)

        manifest = build_dataset_manifest_from_directory(raw_root, "filosax")

        assert manifest.dataset_id == "filosax"
        paths = [entry.relative_path for entry in manifest.files]
        assert paths == sorted(paths)
        assert "P1/take1.wav" in paths
        expected_sha256 = hashlib.sha256(b"synthetic-audio-one").hexdigest()
        entry = next(e for e in manifest.files if e.relative_path == "P1/take1.wav")
        assert entry.sha256 == expected_sha256
        assert entry.size_bytes == len(b"synthetic-audio-one")

    def test_rebuilding_unchanged_directory_is_identical(self, tmp_path: Path) -> None:
        raw_root = tmp_path / "raw"
        write_synthetic_raw_files(raw_root)

        first = build_dataset_manifest_from_directory(raw_root, "filosax")
        second = build_dataset_manifest_from_directory(raw_root, "filosax")

        assert first == second

    def test_rejects_missing_directory(self, tmp_path: Path) -> None:
        with pytest.raises(DatasetDirectoryNotFoundError):
            build_dataset_manifest_from_directory(tmp_path / "missing", "filosax")

    def test_rejects_empty_directory(self, tmp_path: Path) -> None:
        raw_root = tmp_path / "raw"
        raw_root.mkdir()
        with pytest.raises(InvalidDatasetManifestError):
            build_dataset_manifest_from_directory(raw_root, "filosax")


class TestDatasetManifestJsonRoundTrip:
    def test_round_trip_preserves_manifest(self, tmp_path: Path) -> None:
        raw_root = tmp_path / "raw"
        write_synthetic_raw_files(raw_root)
        manifest = build_dataset_manifest_from_directory(raw_root, "filosax")
        manifest_path = tmp_path / "manifest.json"

        write_dataset_manifest_json(manifest, manifest_path)
        loaded = load_dataset_manifest_json(manifest_path)

        assert loaded == manifest

    def test_writing_twice_is_byte_identical(self, tmp_path: Path) -> None:
        raw_root = tmp_path / "raw"
        write_synthetic_raw_files(raw_root)
        manifest = build_dataset_manifest_from_directory(raw_root, "filosax")

        first_path = tmp_path / "first.json"
        second_path = tmp_path / "second.json"
        write_dataset_manifest_json(manifest, first_path)
        write_dataset_manifest_json(manifest, second_path)

        assert first_path.read_text(encoding="utf-8") == second_path.read_text(encoding="utf-8")

    def test_rejects_duplicate_json_keys(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text(
            '{"schema_version": "1.0", "schema_version": "1.0", "dataset_id": "filosax", '
            '"files": []}',
            encoding="utf-8",
        )
        with pytest.raises(InvalidDatasetManifestJsonError):
            load_dataset_manifest_json(path)

    def test_rejects_unknown_fields(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text(
            '{"schema_version": "1.0", "dataset_id": "filosax", "files": [], "extra": true}',
            encoding="utf-8",
        )
        with pytest.raises(InvalidDatasetManifestJsonError):
            load_dataset_manifest_json(path)

    def test_rejects_non_utf8_file(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_bytes(b"\xff\xfe\x00\x01")
        with pytest.raises(InvalidDatasetManifestJsonError):
            load_dataset_manifest_json(path)
