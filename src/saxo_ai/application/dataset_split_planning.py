from __future__ import annotations

import hashlib
from collections.abc import Callable

from saxo_ai.domain.dataset_manifest import DatasetManifest
from saxo_ai.domain.dataset_splits import (
    DATASET_SPLIT_PLAN_SCHEMA_VERSION,
    DatasetSplitAssignment,
    DatasetSplitName,
    DatasetSplitPlan,
    DatasetSplitProportions,
)

GroupKeyFn = Callable[[str], str]

_UINT64_RANGE = 2**64


def top_level_directory_group_key(relative_path: str) -> str:
    """Group by the first path segment, e.g. one group per prepared piece/session folder."""

    return relative_path.split("/", maxsplit=1)[0]


def _bucket_fraction(seed: str, group_key: str) -> float:
    digest = hashlib.sha256(f"{seed}:{group_key}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / _UINT64_RANGE


class AssignDatasetSplits:
    """Deterministically assign whole groups to train/validation/test, never splitting a group."""

    def __init__(self, *, proportions: DatasetSplitProportions, seed: str) -> None:
        if not isinstance(seed, str) or not seed:
            raise ValueError("seed must be a non-empty string")
        self._proportions = proportions
        self._seed = seed

    def execute(self, manifest: DatasetManifest, *, group_key: GroupKeyFn) -> DatasetSplitPlan:
        group_split: dict[str, DatasetSplitName] = {}
        assignments: list[DatasetSplitAssignment] = []
        for entry in manifest.files:
            key = group_key(entry.relative_path)
            split = group_split.get(key)
            if split is None:
                split = self._split_for_group(key)
                group_split[key] = split
            assignments.append(
                DatasetSplitAssignment(
                    relative_path=entry.relative_path, group_key=key, split=split
                )
            )
        return DatasetSplitPlan(
            schema_version=DATASET_SPLIT_PLAN_SCHEMA_VERSION,
            dataset_id=manifest.dataset_id,
            proportions=self._proportions,
            assignments=tuple(sorted(assignments, key=lambda item: item.relative_path)),
        )

    def _split_for_group(self, group_key: str) -> DatasetSplitName:
        fraction = _bucket_fraction(self._seed, group_key)
        train_edge = self._proportions.train
        validation_edge = train_edge + self._proportions.validation
        if fraction < train_edge:
            return DatasetSplitName.TRAIN
        if fraction < validation_edge:
            return DatasetSplitName.VALIDATION
        return DatasetSplitName.TEST
