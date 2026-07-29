from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

DATASET_SPLIT_PLAN_SCHEMA_VERSION = "1.0"

_DATASET_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_PROPORTION_TOLERANCE = 1e-6


class InvalidDatasetSplitPlanError(ValueError):
    """Raised when a dataset split plan violates the leakage-safe grouping contract."""


class DatasetSplitName(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


def _require_proportion(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidDatasetSplitPlanError(f"{field_name} must be a number")
    if not (0.0 < value < 1.0):
        raise InvalidDatasetSplitPlanError(f"{field_name} must be strictly between 0 and 1")
    return float(value)


@dataclass(frozen=True, slots=True)
class DatasetSplitProportions:
    train: float
    validation: float
    test: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "train", _require_proportion("train", self.train))
        object.__setattr__(self, "validation", _require_proportion("validation", self.validation))
        object.__setattr__(self, "test", _require_proportion("test", self.test))
        total = self.train + self.validation + self.test
        if abs(total - 1.0) > _PROPORTION_TOLERANCE:
            raise InvalidDatasetSplitPlanError("train, validation and test must sum to 1.0")


@dataclass(frozen=True, slots=True)
class DatasetSplitAssignment:
    relative_path: str
    group_key: str
    split: DatasetSplitName

    def __post_init__(self) -> None:
        if not isinstance(self.relative_path, str) or not self.relative_path:
            raise InvalidDatasetSplitPlanError("relative_path must be a non-empty string")
        if not isinstance(self.group_key, str) or not self.group_key:
            raise InvalidDatasetSplitPlanError("group_key must be a non-empty string")
        if not isinstance(self.split, DatasetSplitName):
            raise InvalidDatasetSplitPlanError("split is not supported")


@dataclass(frozen=True, slots=True)
class DatasetSplitPlan:
    schema_version: str
    dataset_id: str
    proportions: DatasetSplitProportions
    assignments: tuple[DatasetSplitAssignment, ...]

    def __post_init__(self) -> None:
        if self.schema_version != DATASET_SPLIT_PLAN_SCHEMA_VERSION:
            raise InvalidDatasetSplitPlanError(
                f"schema_version must be {DATASET_SPLIT_PLAN_SCHEMA_VERSION}"
            )
        if not isinstance(self.dataset_id, str) or _DATASET_ID.fullmatch(self.dataset_id) is None:
            raise InvalidDatasetSplitPlanError(
                "dataset_id must be a safe stable lowercase identifier"
            )
        if not isinstance(self.proportions, DatasetSplitProportions):
            raise InvalidDatasetSplitPlanError("proportions must be DatasetSplitProportions")
        if not isinstance(self.assignments, tuple) or not self.assignments:
            raise InvalidDatasetSplitPlanError("assignments must be a non-empty immutable tuple")
        if any(not isinstance(item, DatasetSplitAssignment) for item in self.assignments):
            raise InvalidDatasetSplitPlanError(
                "assignments must contain DatasetSplitAssignment values"
            )
        paths = tuple(item.relative_path for item in self.assignments)
        if len(set(paths)) != len(paths):
            raise InvalidDatasetSplitPlanError("relative_path values must be unique")
        if paths != tuple(sorted(paths)):
            raise InvalidDatasetSplitPlanError("assignments must be sorted by relative_path")
        splits_by_group: dict[str, set[DatasetSplitName]] = {}
        for item in self.assignments:
            splits_by_group.setdefault(item.group_key, set()).add(item.split)
        leaking_groups = tuple(
            sorted(group for group, splits in splits_by_group.items() if len(splits) > 1)
        )
        if leaking_groups:
            raise InvalidDatasetSplitPlanError(
                f"groups must not span multiple splits: {', '.join(leaking_groups)}"
            )

    def paths_for(self, split: DatasetSplitName) -> tuple[str, ...]:
        return tuple(item.relative_path for item in self.assignments if item.split is split)

    def group_count_for(self, split: DatasetSplitName) -> int:
        return len({item.group_key for item in self.assignments if item.split is split})
