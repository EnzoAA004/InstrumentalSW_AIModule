from __future__ import annotations

import re
from dataclasses import dataclass

DATASET_MANIFEST_SCHEMA_VERSION = "1.0"

_DATASET_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_RELATIVE_PATH_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


class InvalidDatasetManifestError(ValueError):
    """Raised when dataset manifest metadata violates the versioned contract."""


def _require_dataset_id(field_name: str, value: object) -> str:
    if not isinstance(value, str) or _DATASET_ID.fullmatch(value) is None:
        raise InvalidDatasetManifestError(
            f"{field_name} must be a safe stable lowercase identifier"
        )
    return value


def _require_relative_path(field_name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise InvalidDatasetManifestError(f"{field_name} must be a non-empty string")
    if value.startswith("/") or ":" in value or "\\" in value:
        raise InvalidDatasetManifestError(f"{field_name} must be a safe POSIX-relative path")
    segments = value.split("/")
    if any(_RELATIVE_PATH_SEGMENT.fullmatch(segment) is None for segment in segments):
        raise InvalidDatasetManifestError(f"{field_name} must not contain empty or unsafe segments")
    if any(segment in {".", ".."} for segment in segments):
        raise InvalidDatasetManifestError(f"{field_name} must not contain traversal segments")
    return value


def _require_size_bytes(field_name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidDatasetManifestError(f"{field_name} must be an integer")
    if value < 0:
        raise InvalidDatasetManifestError(f"{field_name} must not be negative")
    return value


def _require_sha256(field_name: str, value: object) -> str:
    if not isinstance(value, str) or _SHA256_HEX.fullmatch(value) is None:
        raise InvalidDatasetManifestError(
            f"{field_name} must be a lowercase 64-character SHA-256 hex digest"
        )
    return value


@dataclass(frozen=True, slots=True)
class DatasetManifestEntry:
    relative_path: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "relative_path",
            _require_relative_path("relative_path", self.relative_path),
        )
        object.__setattr__(self, "size_bytes", _require_size_bytes("size_bytes", self.size_bytes))
        object.__setattr__(self, "sha256", _require_sha256("sha256", self.sha256))


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    schema_version: str
    dataset_id: str
    files: tuple[DatasetManifestEntry, ...]

    def __post_init__(self) -> None:
        if self.schema_version != DATASET_MANIFEST_SCHEMA_VERSION:
            raise InvalidDatasetManifestError(
                f"schema_version must be {DATASET_MANIFEST_SCHEMA_VERSION}"
            )
        object.__setattr__(self, "dataset_id", _require_dataset_id("dataset_id", self.dataset_id))
        if not isinstance(self.files, tuple) or not self.files:
            raise InvalidDatasetManifestError("files must be a non-empty immutable tuple")
        if any(not isinstance(entry, DatasetManifestEntry) for entry in self.files):
            raise InvalidDatasetManifestError("files must contain DatasetManifestEntry values")
        paths = tuple(entry.relative_path for entry in self.files)
        if len(set(paths)) != len(paths):
            raise InvalidDatasetManifestError("relative_path values must be unique")
        if paths != tuple(sorted(paths)):
            raise InvalidDatasetManifestError("files must be sorted by relative_path")


@dataclass(frozen=True, slots=True)
class DatasetManifestComparison:
    missing_paths: tuple[str, ...]
    unexpected_paths: tuple[str, ...]
    mismatched_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("missing_paths", "unexpected_paths", "mismatched_paths"):
            value = getattr(self, field_name)
            if not isinstance(value, tuple) or any(not isinstance(item, str) for item in value):
                raise InvalidDatasetManifestError(f"{field_name} must be a tuple of strings")
            if value != tuple(sorted(value)):
                raise InvalidDatasetManifestError(f"{field_name} must be sorted")

    @property
    def is_reproducible(self) -> bool:
        return not (self.missing_paths or self.unexpected_paths or self.mismatched_paths)


def compare_dataset_manifests(
    expected: DatasetManifest, actual: DatasetManifest
) -> DatasetManifestComparison:
    if not isinstance(expected, DatasetManifest) or not isinstance(actual, DatasetManifest):
        raise InvalidDatasetManifestError("comparison requires two DatasetManifest values")
    if expected.dataset_id != actual.dataset_id:
        raise InvalidDatasetManifestError(
            "manifests describe different dataset_id values and cannot be compared"
        )
    expected_by_path = {entry.relative_path: entry for entry in expected.files}
    actual_by_path = {entry.relative_path: entry for entry in actual.files}
    expected_paths = frozenset(expected_by_path)
    actual_paths = frozenset(actual_by_path)
    mismatched = tuple(
        sorted(
            path
            for path in expected_paths & actual_paths
            if expected_by_path[path].sha256 != actual_by_path[path].sha256
            or expected_by_path[path].size_bytes != actual_by_path[path].size_bytes
        )
    )
    return DatasetManifestComparison(
        missing_paths=tuple(sorted(expected_paths - actual_paths)),
        unexpected_paths=tuple(sorted(actual_paths - expected_paths)),
        mismatched_paths=mismatched,
    )
