from __future__ import annotations

from pathlib import Path

import pytest

from saxo_ai.domain.dataset_splits import (
    DatasetSplitAssignment,
    DatasetSplitName,
    DatasetSplitPlan,
    DatasetSplitProportions,
)
from saxo_ai.infrastructure.dataset_split_plan_json import (
    InvalidDatasetSplitPlanJsonError,
    load_dataset_split_plan_json,
    write_dataset_split_plan_json,
)


def sample_plan() -> DatasetSplitPlan:
    return DatasetSplitPlan(
        schema_version="1.0",
        dataset_id="filosax",
        proportions=DatasetSplitProportions(train=0.7, validation=0.15, test=0.15),
        assignments=(
            DatasetSplitAssignment(
                relative_path="P1/a.wav", group_key="P1", split=DatasetSplitName.TRAIN
            ),
            DatasetSplitAssignment(
                relative_path="P2/a.wav", group_key="P2", split=DatasetSplitName.TEST
            ),
        ),
    )


class TestDatasetSplitPlanJsonRoundTrip:
    def test_round_trip_preserves_plan(self, tmp_path: Path) -> None:
        plan = sample_plan()
        path = tmp_path / "plan.json"

        write_dataset_split_plan_json(plan, path)
        loaded = load_dataset_split_plan_json(path)

        assert loaded == plan

    def test_writing_twice_is_byte_identical(self, tmp_path: Path) -> None:
        plan = sample_plan()
        first_path = tmp_path / "first.json"
        second_path = tmp_path / "second.json"

        write_dataset_split_plan_json(plan, first_path)
        write_dataset_split_plan_json(plan, second_path)

        assert first_path.read_text(encoding="utf-8") == second_path.read_text(encoding="utf-8")

    def test_rejects_unknown_split_value(self, tmp_path: Path) -> None:
        path = tmp_path / "plan.json"
        path.write_text(
            '{"schema_version": "1.0", "dataset_id": "filosax", '
            '"proportions": {"train": 0.7, "validation": 0.15, "test": 0.15}, '
            '"assignments": [{"relative_path": "a.wav", "group_key": "a", "split": "bogus"}]}',
            encoding="utf-8",
        )
        with pytest.raises(InvalidDatasetSplitPlanJsonError):
            load_dataset_split_plan_json(path)

    def test_rejects_duplicate_json_keys(self, tmp_path: Path) -> None:
        path = tmp_path / "plan.json"
        path.write_text(
            '{"schema_version": "1.0", "schema_version": "1.0", "dataset_id": "filosax", '
            '"proportions": {"train": 0.7, "validation": 0.15, "test": 0.15}, "assignments": []}',
            encoding="utf-8",
        )
        with pytest.raises(InvalidDatasetSplitPlanJsonError):
            load_dataset_split_plan_json(path)

    def test_rejects_non_path_argument(self) -> None:
        with pytest.raises(InvalidDatasetSplitPlanJsonError):
            load_dataset_split_plan_json("plan.json")  # type: ignore[arg-type]

    def test_rejects_non_utf8_file(self, tmp_path: Path) -> None:
        path = tmp_path / "plan.json"
        path.write_bytes(b"\xff\xfe\x00\x01")
        with pytest.raises(InvalidDatasetSplitPlanJsonError):
            load_dataset_split_plan_json(path)

    def test_rejects_invalid_json_syntax(self, tmp_path: Path) -> None:
        path = tmp_path / "plan.json"
        path.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(InvalidDatasetSplitPlanJsonError):
            load_dataset_split_plan_json(path)

    def test_rejects_missing_top_level_field(self, tmp_path: Path) -> None:
        path = tmp_path / "plan.json"
        path.write_text(
            '{"schema_version": "1.0", "dataset_id": "filosax", "assignments": []}',
            encoding="utf-8",
        )
        with pytest.raises(InvalidDatasetSplitPlanJsonError):
            load_dataset_split_plan_json(path)

    def test_rejects_unknown_top_level_field(self, tmp_path: Path) -> None:
        path = tmp_path / "plan.json"
        path.write_text(
            '{"schema_version": "1.0", "dataset_id": "filosax", '
            '"proportions": {"train": 0.7, "validation": 0.15, "test": 0.15}, '
            '"assignments": [], "extra": true}',
            encoding="utf-8",
        )
        with pytest.raises(InvalidDatasetSplitPlanJsonError):
            load_dataset_split_plan_json(path)

    def test_rejects_unknown_proportions_field(self, tmp_path: Path) -> None:
        path = tmp_path / "plan.json"
        path.write_text(
            '{"schema_version": "1.0", "dataset_id": "filosax", '
            '"proportions": {"train": 0.7, "validation": 0.15, "test": 0.15, "extra": 1}, '
            '"assignments": []}',
            encoding="utf-8",
        )
        with pytest.raises(InvalidDatasetSplitPlanJsonError):
            load_dataset_split_plan_json(path)

    def test_rejects_unknown_assignment_field(self, tmp_path: Path) -> None:
        path = tmp_path / "plan.json"
        path.write_text(
            '{"schema_version": "1.0", "dataset_id": "filosax", '
            '"proportions": {"train": 0.7, "validation": 0.15, "test": 0.15}, '
            '"assignments": [{"relative_path": "a.wav", "group_key": "a", "split": "train", '
            '"extra": 1}]}',
            encoding="utf-8",
        )
        with pytest.raises(InvalidDatasetSplitPlanJsonError):
            load_dataset_split_plan_json(path)

    def test_rejects_non_number_proportion(self, tmp_path: Path) -> None:
        path = tmp_path / "plan.json"
        path.write_text(
            '{"schema_version": "1.0", "dataset_id": "filosax", '
            '"proportions": {"train": "0.7", "validation": 0.15, "test": 0.15}, '
            '"assignments": []}',
            encoding="utf-8",
        )
        with pytest.raises(InvalidDatasetSplitPlanJsonError):
            load_dataset_split_plan_json(path)

    def test_rejects_non_object_plan(self, tmp_path: Path) -> None:
        path = tmp_path / "plan.json"
        path.write_text("[]", encoding="utf-8")
        with pytest.raises(InvalidDatasetSplitPlanJsonError):
            load_dataset_split_plan_json(path)

    def test_rejects_non_list_assignments(self, tmp_path: Path) -> None:
        path = tmp_path / "plan.json"
        path.write_text(
            '{"schema_version": "1.0", "dataset_id": "filosax", '
            '"proportions": {"train": 0.7, "validation": 0.15, "test": 0.15}, '
            '"assignments": "not-a-list"}',
            encoding="utf-8",
        )
        with pytest.raises(InvalidDatasetSplitPlanJsonError):
            load_dataset_split_plan_json(path)
