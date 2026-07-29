from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from saxo_ai.domain.dataset_manifest import (
    DATASET_MANIFEST_SCHEMA_VERSION,
    DatasetManifest,
    DatasetManifestEntry,
    InvalidDatasetManifestError,
)

_MANIFEST_FIELDS = frozenset({"schema_version", "dataset_id", "files"})
_ENTRY_FIELDS = frozenset({"relative_path", "size_bytes", "sha256"})
_CHUNK_SIZE = 64 * 1024


class InvalidDatasetManifestJsonError(ValueError):
    """Raised when JSON cannot be decoded into the exact dataset manifest schema."""


class DatasetDirectoryNotFoundError(ValueError):
    """Raised when the raw dataset directory to manifest does not exist."""


def build_dataset_manifest_from_directory(root: Path, dataset_id: str) -> DatasetManifest:
    """Walk a raw dataset directory and hash every file into a deterministic manifest."""

    if not isinstance(root, Path):
        raise TypeError("root must be pathlib.Path")
    if not root.is_dir():
        raise DatasetDirectoryNotFoundError(f"raw dataset directory not found: {root}")
    entries = tuple(
        sorted(
            (
                _manifest_entry(root, file_path)
                for file_path in root.rglob("*")
                if file_path.is_file()
            ),
            key=lambda entry: entry.relative_path,
        )
    )
    if not entries:
        raise InvalidDatasetManifestError("raw dataset directory contains no files to manifest")
    return DatasetManifest(
        schema_version=DATASET_MANIFEST_SCHEMA_VERSION,
        dataset_id=dataset_id,
        files=entries,
    )


def _manifest_entry(root: Path, file_path: Path) -> DatasetManifestEntry:
    digest = hashlib.sha256()
    size_bytes = 0
    with file_path.open("rb") as stream:
        while True:
            chunk = stream.read(_CHUNK_SIZE)
            if chunk == b"":
                break
            size_bytes += len(chunk)
            digest.update(chunk)
    relative_path = file_path.relative_to(root).as_posix()
    return DatasetManifestEntry(
        relative_path=relative_path, size_bytes=size_bytes, sha256=digest.hexdigest()
    )


def write_dataset_manifest_json(manifest: DatasetManifest, path: Path) -> None:
    """Serialize a manifest deterministically so it is stable across regenerations."""

    payload = {
        "schema_version": manifest.schema_version,
        "dataset_id": manifest.dataset_id,
        "files": [
            {
                "relative_path": entry.relative_path,
                "size_bytes": entry.size_bytes,
                "sha256": entry.sha256,
            }
            for entry in manifest.files
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_dataset_manifest_json(path: Path) -> DatasetManifest:
    """Load one UTF-8 JSON manifest using exact fields and immutable domain contracts."""

    if not isinstance(path, Path):
        raise InvalidDatasetManifestJsonError("manifest path must be pathlib.Path")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise InvalidDatasetManifestJsonError("manifest file could not be read as UTF-8") from error
    try:
        parsed = cast(object, json.loads(text, object_pairs_hook=_reject_duplicate_keys))
    except json.JSONDecodeError as error:
        raise InvalidDatasetManifestJsonError("manifest file must contain valid JSON") from error
    try:
        return _decode_manifest(parsed)
    except InvalidDatasetManifestError as error:
        raise InvalidDatasetManifestJsonError(str(error)) from error


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidDatasetManifestJsonError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _decode_manifest(value: object) -> DatasetManifest:
    payload = _require_object(value, "manifest")
    _require_exact_fields(payload, _MANIFEST_FIELDS, "manifest")
    files = tuple(
        _decode_entry(item, f"files[{index}]")
        for index, item in enumerate(_require_list(payload["files"], "files"))
    )
    return DatasetManifest(
        schema_version=_require_string(payload["schema_version"], "schema_version"),
        dataset_id=_require_string(payload["dataset_id"], "dataset_id"),
        files=files,
    )


def _decode_entry(value: object, context: str) -> DatasetManifestEntry:
    payload = _require_object(value, context)
    _require_exact_fields(payload, _ENTRY_FIELDS, context)
    size_bytes = payload["size_bytes"]
    if isinstance(size_bytes, bool) or not isinstance(size_bytes, int):
        raise InvalidDatasetManifestJsonError(f"{context}.size_bytes must be an integer")
    return DatasetManifestEntry(
        relative_path=_require_string(payload["relative_path"], f"{context}.relative_path"),
        size_bytes=size_bytes,
        sha256=_require_string(payload["sha256"], f"{context}.sha256"),
    )


def _require_object(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise InvalidDatasetManifestJsonError(f"{context} must be an object")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise InvalidDatasetManifestJsonError(f"{context} keys must be strings")
        result[key] = item
    return result


def _require_list(value: object, context: str) -> list[object]:
    if not isinstance(value, list):
        raise InvalidDatasetManifestJsonError(f"{context} must be an array")
    return list(value)


def _require_string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise InvalidDatasetManifestJsonError(f"{context} must be a non-empty string")
    return value


def _require_exact_fields(
    payload: dict[str, object], expected: frozenset[str], context: str
) -> None:
    actual = frozenset(payload)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise InvalidDatasetManifestJsonError(
            f"{context} is missing fields: {', '.join(sorted(missing))}"
        )
    if unknown:
        raise InvalidDatasetManifestJsonError(
            f"{context} contains unknown fields: {', '.join(sorted(unknown))}"
        )
