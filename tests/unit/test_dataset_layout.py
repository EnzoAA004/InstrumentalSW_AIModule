from __future__ import annotations

import pytest

from saxo_ai.domain.dataset_layout import (
    InvalidDatasetLayoutError,
    validate_distinct_dataset_roots,
)


class TestValidateDistinctDatasetRoots:
    def test_accepts_sibling_roots(self) -> None:
        validate_distinct_dataset_roots("/data/raw/filosax", "/data/processed/filosax")

    def test_rejects_identical_roots(self) -> None:
        with pytest.raises(InvalidDatasetLayoutError):
            validate_distinct_dataset_roots("/data/raw/filosax", "/data/raw/filosax")

    def test_rejects_processed_nested_inside_raw(self) -> None:
        with pytest.raises(InvalidDatasetLayoutError):
            validate_distinct_dataset_roots("/data/raw/filosax", "/data/raw/filosax/processed")

    def test_rejects_raw_nested_inside_processed(self) -> None:
        with pytest.raises(InvalidDatasetLayoutError):
            validate_distinct_dataset_roots(
                "/data/processed/filosax/raw", "/data/processed/filosax"
            )

    def test_rejects_relative_root(self) -> None:
        with pytest.raises(InvalidDatasetLayoutError):
            validate_distinct_dataset_roots("data/raw/filosax", "/data/processed/filosax")

    def test_rejects_windows_separators(self) -> None:
        with pytest.raises(InvalidDatasetLayoutError):
            validate_distinct_dataset_roots("C:\\data\\raw", "/data/processed/filosax")

    def test_rejects_unnormalized_root(self) -> None:
        with pytest.raises(InvalidDatasetLayoutError):
            validate_distinct_dataset_roots("/data/raw/../raw/filosax", "/data/processed/filosax")

    def test_accepts_paths_that_share_a_common_prefix_segment(self) -> None:
        validate_distinct_dataset_roots("/data/raw-filosax", "/data/raw-filosax-processed")
