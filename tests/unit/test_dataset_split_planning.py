from __future__ import annotations

import pytest

from saxo_ai.application.dataset_split_planning import (
    AssignDatasetSplits,
    top_level_directory_group_key,
)
from saxo_ai.domain.dataset_manifest import DatasetManifest, DatasetManifestEntry
from saxo_ai.domain.dataset_splits import DatasetSplitName, DatasetSplitProportions

SHA = "a" * 64


def manifest_with_pieces(piece_count: int, files_per_piece: int = 2) -> DatasetManifest:
    files = tuple(
        DatasetManifestEntry(
            relative_path=f"piece-{piece:03d}/file-{file}.wav", size_bytes=1, sha256=SHA
        )
        for piece in range(piece_count)
        for file in range(files_per_piece)
    )
    return DatasetManifest(schema_version="1.0", dataset_id="filosax", files=files)


class TestTopLevelDirectoryGroupKey:
    def test_returns_first_segment(self) -> None:
        assert top_level_directory_group_key("piece-001/take1.wav") == "piece-001"

    def test_returns_whole_path_when_no_directory(self) -> None:
        assert top_level_directory_group_key("take1.wav") == "take1.wav"


class TestAssignDatasetSplits:
    def test_rejects_empty_seed(self) -> None:
        with pytest.raises(ValueError, match="seed"):
            AssignDatasetSplits(
                proportions=DatasetSplitProportions(train=0.7, validation=0.15, test=0.15),
                seed="",
            )

    def test_every_file_is_assigned(self) -> None:
        manifest = manifest_with_pieces(20)
        use_case = AssignDatasetSplits(
            proportions=DatasetSplitProportions(train=0.7, validation=0.15, test=0.15),
            seed="test-seed",
        )
        plan = use_case.execute(manifest, group_key=top_level_directory_group_key)
        assert len(plan.assignments) == len(manifest.files)

    def test_all_files_of_a_group_land_in_the_same_split(self) -> None:
        manifest = manifest_with_pieces(20, files_per_piece=5)
        use_case = AssignDatasetSplits(
            proportions=DatasetSplitProportions(train=0.7, validation=0.15, test=0.15),
            seed="test-seed",
        )
        plan = use_case.execute(manifest, group_key=top_level_directory_group_key)
        splits_by_group: dict[str, set[DatasetSplitName]] = {}
        for item in plan.assignments:
            splits_by_group.setdefault(item.group_key, set()).add(item.split)
        assert all(len(splits) == 1 for splits in splits_by_group.values())

    def test_same_seed_is_deterministic_across_runs(self) -> None:
        manifest = manifest_with_pieces(20)
        proportions = DatasetSplitProportions(train=0.7, validation=0.15, test=0.15)
        first = AssignDatasetSplits(proportions=proportions, seed="fixed-seed").execute(
            manifest, group_key=top_level_directory_group_key
        )
        second = AssignDatasetSplits(proportions=proportions, seed="fixed-seed").execute(
            manifest, group_key=top_level_directory_group_key
        )
        assert first == second

    def test_different_seeds_can_change_the_partition(self) -> None:
        manifest = manifest_with_pieces(50)
        proportions = DatasetSplitProportions(train=0.7, validation=0.15, test=0.15)
        first = AssignDatasetSplits(proportions=proportions, seed="seed-one").execute(
            manifest, group_key=top_level_directory_group_key
        )
        second = AssignDatasetSplits(proportions=proportions, seed="seed-two").execute(
            manifest, group_key=top_level_directory_group_key
        )
        assert first.assignments != second.assignments

    def test_proportions_are_roughly_respected_with_many_groups(self) -> None:
        manifest = manifest_with_pieces(500)
        use_case = AssignDatasetSplits(
            proportions=DatasetSplitProportions(train=0.7, validation=0.15, test=0.15),
            seed="statistical-seed",
        )
        plan = use_case.execute(manifest, group_key=top_level_directory_group_key)
        total_groups = 500
        train_share = plan.group_count_for(DatasetSplitName.TRAIN) / total_groups
        assert 0.6 < train_share < 0.8
