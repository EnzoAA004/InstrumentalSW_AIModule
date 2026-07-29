from __future__ import annotations

import pytest

from saxo_ai.domain.dataset_manifest import (
    DatasetManifest,
    DatasetManifestComparison,
    DatasetManifestEntry,
    InvalidDatasetManifestError,
    compare_dataset_manifests,
)

VALID_SHA256 = "a" * 64
OTHER_SHA256 = "b" * 64


def entry(
    relative_path: str = "P1/take1.wav", size_bytes: int = 10, sha256: str = VALID_SHA256
) -> DatasetManifestEntry:
    return DatasetManifestEntry(relative_path=relative_path, size_bytes=size_bytes, sha256=sha256)


def manifest(*entries: DatasetManifestEntry, dataset_id: str = "filosax") -> DatasetManifest:
    return DatasetManifest(schema_version="1.0", dataset_id=dataset_id, files=entries)


class TestDatasetManifestEntry:
    def test_accepts_valid_entry(self) -> None:
        value = entry()
        assert value.relative_path == "P1/take1.wav"
        assert value.sha256 == VALID_SHA256

    @pytest.mark.parametrize(
        "relative_path",
        ["", "/abs/path", "C:/win.wav", "a\\b.wav", "../escape.wav", "a/../b.wav", "a//b.wav"],
    )
    def test_rejects_unsafe_relative_path(self, relative_path: str) -> None:
        with pytest.raises(InvalidDatasetManifestError):
            entry(relative_path=relative_path)

    def test_rejects_negative_size(self) -> None:
        with pytest.raises(InvalidDatasetManifestError):
            entry(size_bytes=-1)

    def test_rejects_non_integer_size(self) -> None:
        with pytest.raises(InvalidDatasetManifestError):
            entry(size_bytes=True)

    @pytest.mark.parametrize("sha256", ["", "not-hex", "a" * 63, "A" * 64])
    def test_rejects_invalid_sha256(self, sha256: str) -> None:
        with pytest.raises(InvalidDatasetManifestError):
            entry(sha256=sha256)


class TestDatasetManifest:
    def test_accepts_sorted_unique_files(self) -> None:
        value = manifest(entry(relative_path="a.wav"), entry(relative_path="b.wav"))
        assert len(value.files) == 2

    def test_rejects_wrong_schema_version(self) -> None:
        with pytest.raises(InvalidDatasetManifestError):
            DatasetManifest(schema_version="2.0", dataset_id="filosax", files=(entry(),))

    def test_rejects_empty_files(self) -> None:
        with pytest.raises(InvalidDatasetManifestError):
            DatasetManifest(schema_version="1.0", dataset_id="filosax", files=())

    def test_rejects_duplicate_paths(self) -> None:
        with pytest.raises(InvalidDatasetManifestError):
            manifest(entry(relative_path="a.wav"), entry(relative_path="a.wav"))

    def test_rejects_unsorted_files(self) -> None:
        with pytest.raises(InvalidDatasetManifestError):
            manifest(entry(relative_path="b.wav"), entry(relative_path="a.wav"))

    def test_rejects_invalid_dataset_id(self) -> None:
        with pytest.raises(InvalidDatasetManifestError):
            manifest(entry(), dataset_id="Filosax_Bad")


class TestCompareDatasetManifests:
    def test_identical_manifests_are_reproducible(self) -> None:
        left = manifest(entry(relative_path="a.wav"))
        right = manifest(entry(relative_path="a.wav"))
        result = compare_dataset_manifests(left, right)
        assert result.is_reproducible
        assert result == DatasetManifestComparison((), (), ())

    def test_detects_missing_path(self) -> None:
        expected = manifest(entry(relative_path="a.wav"), entry(relative_path="b.wav"))
        actual = manifest(entry(relative_path="a.wav"))
        result = compare_dataset_manifests(expected, actual)
        assert result.missing_paths == ("b.wav",)
        assert not result.is_reproducible

    def test_detects_unexpected_path(self) -> None:
        expected = manifest(entry(relative_path="a.wav"))
        actual = manifest(entry(relative_path="a.wav"), entry(relative_path="b.wav"))
        result = compare_dataset_manifests(expected, actual)
        assert result.unexpected_paths == ("b.wav",)

    def test_detects_mismatched_checksum(self) -> None:
        expected = manifest(entry(relative_path="a.wav", sha256=VALID_SHA256))
        actual = manifest(entry(relative_path="a.wav", sha256=OTHER_SHA256))
        result = compare_dataset_manifests(expected, actual)
        assert result.mismatched_paths == ("a.wav",)

    def test_detects_mismatched_size(self) -> None:
        expected = manifest(entry(relative_path="a.wav", size_bytes=1))
        actual = manifest(entry(relative_path="a.wav", size_bytes=2))
        result = compare_dataset_manifests(expected, actual)
        assert result.mismatched_paths == ("a.wav",)

    def test_rejects_different_dataset_ids(self) -> None:
        left = manifest(entry(), dataset_id="filosax")
        right = manifest(entry(), dataset_id="other-dataset")
        with pytest.raises(InvalidDatasetManifestError):
            compare_dataset_manifests(left, right)
