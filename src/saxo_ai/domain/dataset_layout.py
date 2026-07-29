from __future__ import annotations


class InvalidDatasetLayoutError(ValueError):
    """Raised when a raw/processed dataset directory layout violates separation rules."""


def _require_normalized_absolute_posix_path(field_name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise InvalidDatasetLayoutError(f"{field_name} must be a non-empty string")
    if "\\" in value:
        raise InvalidDatasetLayoutError(f"{field_name} must use POSIX separators")
    if not value.startswith("/"):
        raise InvalidDatasetLayoutError(f"{field_name} must be an absolute path")
    segments = [segment for segment in value.split("/") if segment != ""]
    if any(segment in {".", ".."} for segment in segments):
        raise InvalidDatasetLayoutError(f"{field_name} must already be normalized")
    return "/" + "/".join(segments)


def validate_distinct_dataset_roots(raw_root: str, processed_root: str) -> None:
    """Reject overlapping raw/processed dataset roots to keep sources and derived data apart."""

    raw = _require_normalized_absolute_posix_path("raw_root", raw_root)
    processed = _require_normalized_absolute_posix_path("processed_root", processed_root)
    if raw == processed:
        raise InvalidDatasetLayoutError("raw_root and processed_root must not be the same path")
    raw_segments = raw.split("/")
    processed_segments = processed.split("/")
    shorter, longer = sorted((raw_segments, processed_segments), key=len)
    if longer[: len(shorter)] == shorter:
        raise InvalidDatasetLayoutError(
            "raw_root and processed_root must not be nested inside one another"
        )
