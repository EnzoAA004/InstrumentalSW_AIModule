from __future__ import annotations

import pytest

from saxo_ai.domain.dataset_splits import (
    DatasetSplitAssignment,
    DatasetSplitName,
    DatasetSplitPlan,
    DatasetSplitProportions,
    InvalidDatasetSplitPlanError,
)


def assignment(
    relative_path: str = "P1/a.wav",
    group_key: str = "P1",
    split: DatasetSplitName = DatasetSplitName.TRAIN,
) -> DatasetSplitAssignment:
    return DatasetSplitAssignment(relative_path=relative_path, group_key=group_key, split=split)


def plan(*assignments: DatasetSplitAssignment, dataset_id: str = "filosax") -> DatasetSplitPlan:
    return DatasetSplitPlan(
        schema_version="1.0",
        dataset_id=dataset_id,
        proportions=DatasetSplitProportions(train=0.7, validation=0.15, test=0.15),
        assignments=assignments,
    )


class TestDatasetSplitProportions:
    def test_accepts_proportions_summing_to_one(self) -> None:
        DatasetSplitProportions(train=0.7, validation=0.15, test=0.15)

    def test_rejects_proportions_not_summing_to_one(self) -> None:
        with pytest.raises(InvalidDatasetSplitPlanError):
            DatasetSplitProportions(train=0.5, validation=0.2, test=0.2)

    @pytest.mark.parametrize("train", [0.0, 1.0, -0.1, 1.1])
    def test_rejects_out_of_range_proportion(self, train: float) -> None:
        with pytest.raises(InvalidDatasetSplitPlanError):
            DatasetSplitProportions(train=train, validation=0.15, test=0.15)

    def test_rejects_non_numeric_proportion(self) -> None:
        with pytest.raises(InvalidDatasetSplitPlanError):
            DatasetSplitProportions(train="0.7", validation=0.15, test=0.15)  # type: ignore[arg-type]

    def test_rejects_boolean_proportion(self) -> None:
        with pytest.raises(InvalidDatasetSplitPlanError):
            DatasetSplitProportions(train=True, validation=0.15, test=0.15)


class TestDatasetSplitAssignment:
    def test_rejects_empty_relative_path(self) -> None:
        with pytest.raises(InvalidDatasetSplitPlanError):
            assignment(relative_path="")

    def test_rejects_empty_group_key(self) -> None:
        with pytest.raises(InvalidDatasetSplitPlanError):
            assignment(group_key="")

    def test_rejects_unsupported_split(self) -> None:
        with pytest.raises(InvalidDatasetSplitPlanError):
            assignment(split="train")  # type: ignore[arg-type]


class TestDatasetSplitPlan:
    def test_accepts_consistent_plan(self) -> None:
        value = plan(
            assignment(relative_path="P1/a.wav", group_key="P1", split=DatasetSplitName.TRAIN),
            assignment(relative_path="P2/a.wav", group_key="P2", split=DatasetSplitName.TEST),
        )
        assert value.paths_for(DatasetSplitName.TRAIN) == ("P1/a.wav",)
        assert value.group_count_for(DatasetSplitName.TEST) == 1

    def test_rejects_group_spanning_two_splits(self) -> None:
        with pytest.raises(InvalidDatasetSplitPlanError):
            plan(
                assignment(relative_path="P1/a.wav", group_key="P1", split=DatasetSplitName.TRAIN),
                assignment(relative_path="P1/b.wav", group_key="P1", split=DatasetSplitName.TEST),
            )

    def test_rejects_duplicate_relative_path(self) -> None:
        with pytest.raises(InvalidDatasetSplitPlanError):
            plan(
                assignment(relative_path="P1/a.wav", group_key="P1"),
                assignment(relative_path="P1/a.wav", group_key="P1"),
            )

    def test_rejects_unsorted_assignments(self) -> None:
        with pytest.raises(InvalidDatasetSplitPlanError):
            plan(
                assignment(relative_path="b.wav", group_key="B"),
                assignment(relative_path="a.wav", group_key="A"),
            )

    def test_rejects_empty_assignments(self) -> None:
        with pytest.raises(InvalidDatasetSplitPlanError):
            plan()

    def test_rejects_wrong_schema_version(self) -> None:
        with pytest.raises(InvalidDatasetSplitPlanError):
            DatasetSplitPlan(
                schema_version="2.0",
                dataset_id="filosax",
                proportions=DatasetSplitProportions(train=0.7, validation=0.15, test=0.15),
                assignments=(assignment(),),
            )

    def test_rejects_invalid_dataset_id(self) -> None:
        with pytest.raises(InvalidDatasetSplitPlanError):
            plan(assignment(), dataset_id="Filosax_Bad")

    def test_rejects_non_proportions_value(self) -> None:
        with pytest.raises(InvalidDatasetSplitPlanError):
            DatasetSplitPlan(
                schema_version="1.0",
                dataset_id="filosax",
                proportions="not-proportions",  # type: ignore[arg-type]
                assignments=(assignment(),),
            )

    def test_rejects_non_assignment_item(self) -> None:
        with pytest.raises(InvalidDatasetSplitPlanError):
            DatasetSplitPlan(
                schema_version="1.0",
                dataset_id="filosax",
                proportions=DatasetSplitProportions(train=0.7, validation=0.15, test=0.15),
                assignments=("not-an-assignment",),  # type: ignore[arg-type]
            )
