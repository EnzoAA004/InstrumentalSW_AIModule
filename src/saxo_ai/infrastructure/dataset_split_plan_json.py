from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from saxo_ai.domain.dataset_splits import (
    DatasetSplitAssignment,
    DatasetSplitName,
    DatasetSplitPlan,
    DatasetSplitProportions,
    InvalidDatasetSplitPlanError,
)

_PLAN_FIELDS = frozenset({"schema_version", "dataset_id", "proportions", "assignments"})
_PROPORTIONS_FIELDS = frozenset({"train", "validation", "test"})
_ASSIGNMENT_FIELDS = frozenset({"relative_path", "group_key", "split"})


class InvalidDatasetSplitPlanJsonError(ValueError):
    """Raised when JSON cannot be decoded into the exact dataset split plan schema."""


def write_dataset_split_plan_json(plan: DatasetSplitPlan, path: Path) -> None:
    """Serialize a split plan deterministically so it is stable across regenerations."""

    payload = {
        "schema_version": plan.schema_version,
        "dataset_id": plan.dataset_id,
        "proportions": {
            "train": plan.proportions.train,
            "validation": plan.proportions.validation,
            "test": plan.proportions.test,
        },
        "assignments": [
            {
                "relative_path": item.relative_path,
                "group_key": item.group_key,
                "split": item.split.value,
            }
            for item in plan.assignments
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_dataset_split_plan_json(path: Path) -> DatasetSplitPlan:
    """Load one UTF-8 JSON split plan using exact fields and immutable domain contracts."""

    if not isinstance(path, Path):
        raise InvalidDatasetSplitPlanJsonError("split plan path must be pathlib.Path")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise InvalidDatasetSplitPlanJsonError(
            "split plan file could not be read as UTF-8"
        ) from error
    try:
        parsed = cast(object, json.loads(text, object_pairs_hook=_reject_duplicate_keys))
    except json.JSONDecodeError as error:
        raise InvalidDatasetSplitPlanJsonError("split plan file must contain valid JSON") from error
    try:
        return _decode_plan(parsed)
    except InvalidDatasetSplitPlanError as error:
        raise InvalidDatasetSplitPlanJsonError(str(error)) from error


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidDatasetSplitPlanJsonError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _decode_plan(value: object) -> DatasetSplitPlan:
    payload = _require_object(value, "plan")
    _require_exact_fields(payload, _PLAN_FIELDS, "plan")
    assignments = tuple(
        _decode_assignment(item, f"assignments[{index}]")
        for index, item in enumerate(_require_list(payload["assignments"], "assignments"))
    )
    return DatasetSplitPlan(
        schema_version=_require_string(payload["schema_version"], "schema_version"),
        dataset_id=_require_string(payload["dataset_id"], "dataset_id"),
        proportions=_decode_proportions(payload["proportions"], "proportions"),
        assignments=assignments,
    )


def _decode_proportions(value: object, context: str) -> DatasetSplitProportions:
    payload = _require_object(value, context)
    _require_exact_fields(payload, _PROPORTIONS_FIELDS, context)
    return DatasetSplitProportions(
        train=_require_number(payload["train"], f"{context}.train"),
        validation=_require_number(payload["validation"], f"{context}.validation"),
        test=_require_number(payload["test"], f"{context}.test"),
    )


def _decode_assignment(value: object, context: str) -> DatasetSplitAssignment:
    payload = _require_object(value, context)
    _require_exact_fields(payload, _ASSIGNMENT_FIELDS, context)
    split_text = _require_string(payload["split"], f"{context}.split")
    try:
        split = DatasetSplitName(split_text)
    except ValueError as error:
        raise InvalidDatasetSplitPlanJsonError(f"{context}.split is not supported") from error
    return DatasetSplitAssignment(
        relative_path=_require_string(payload["relative_path"], f"{context}.relative_path"),
        group_key=_require_string(payload["group_key"], f"{context}.group_key"),
        split=split,
    )


def _require_object(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise InvalidDatasetSplitPlanJsonError(f"{context} must be an object")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise InvalidDatasetSplitPlanJsonError(f"{context} keys must be strings")
        result[key] = item
    return result


def _require_list(value: object, context: str) -> list[object]:
    if not isinstance(value, list):
        raise InvalidDatasetSplitPlanJsonError(f"{context} must be an array")
    return list(value)


def _require_string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise InvalidDatasetSplitPlanJsonError(f"{context} must be a non-empty string")
    return value


def _require_number(value: object, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidDatasetSplitPlanJsonError(f"{context} must be a number")
    return float(value)


def _require_exact_fields(
    payload: dict[str, object], expected: frozenset[str], context: str
) -> None:
    actual = frozenset(payload)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise InvalidDatasetSplitPlanJsonError(
            f"{context} is missing fields: {', '.join(sorted(missing))}"
        )
    if unknown:
        raise InvalidDatasetSplitPlanJsonError(
            f"{context} contains unknown fields: {', '.join(sorted(unknown))}"
        )
