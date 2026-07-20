from dataclasses import FrozenInstanceError

import pytest

from saxo_ai.domain.note_event_postprocessing import (
    DUPLICATE_POLICY_NAME,
    NOTE_EVENT_POSTPROCESSING_POLICY_VERSION,
    InvalidNoteEventPostProcessingContractError,
    NoteEventPostProcessingReport,
    NoteEventPostProcessingResult,
    NoteEventPostProcessingSettings,
)
from saxo_ai.domain.note_events import NoteEventBatch


def test_settings_defaults_are_versioned_and_deterministic() -> None:
    settings = NoteEventPostProcessingSettings()

    assert settings.minimum_duration_seconds == 0.030
    assert settings.policy_version == NOTE_EVENT_POSTPROCESSING_POLICY_VERSION == "1.0"
    assert settings.duplicate_policy == DUPLICATE_POLICY_NAME
    assert DUPLICATE_POLICY_NAME == "same_pitch_exact_interval_keep_highest_confidence"


def test_settings_normalize_integer_minimum_duration_to_float() -> None:
    settings = NoteEventPostProcessingSettings(minimum_duration_seconds=0)

    assert settings.minimum_duration_seconds == 0.0
    assert isinstance(settings.minimum_duration_seconds, float)


@pytest.mark.parametrize(
    "invalid_value",
    [-0.001, float("nan"), float("inf"), float("-inf"), True, False, "0.03", None],
)
def test_settings_reject_invalid_minimum_duration(invalid_value: object) -> None:
    with pytest.raises(InvalidNoteEventPostProcessingContractError):
        NoteEventPostProcessingSettings(
            minimum_duration_seconds=invalid_value  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [("policy_version", "2.0"), ("duplicate_policy", "approximate")],
)
def test_settings_reject_unsupported_policy_identity(field_name: str, invalid_value: str) -> None:
    arguments = {field_name: invalid_value}

    with pytest.raises(InvalidNoteEventPostProcessingContractError):
        NoteEventPostProcessingSettings(**arguments)  # type: ignore[arg-type]


def test_settings_are_immutable() -> None:
    settings = NoteEventPostProcessingSettings()

    with pytest.raises(FrozenInstanceError):
        settings.minimum_duration_seconds = 0.1  # type: ignore[misc]


def test_report_calculates_total_affected_count() -> None:
    report = NoteEventPostProcessingReport(
        settings=NoteEventPostProcessingSettings(),
        input_event_count=7,
        output_event_count=3,
        short_duration_removed_count=2,
        duplicate_removed_count=2,
        duplicate_group_count=1,
    )

    assert report.affected_event_count == 4


@pytest.mark.parametrize(
    "field_name",
    [
        "input_event_count",
        "output_event_count",
        "short_duration_removed_count",
        "duplicate_removed_count",
        "duplicate_group_count",
    ],
)
def test_report_rejects_negative_counts(field_name: str) -> None:
    arguments = {
        "settings": NoteEventPostProcessingSettings(),
        "input_event_count": 1,
        "output_event_count": 1,
        "short_duration_removed_count": 0,
        "duplicate_removed_count": 0,
        "duplicate_group_count": 0,
    }
    arguments[field_name] = -1

    with pytest.raises(InvalidNoteEventPostProcessingContractError):
        NoteEventPostProcessingReport(**arguments)  # type: ignore[arg-type]


@pytest.mark.parametrize("invalid_count", [True, 1.0, "1", None])
def test_report_rejects_non_integer_counts(invalid_count: object) -> None:
    with pytest.raises(InvalidNoteEventPostProcessingContractError):
        NoteEventPostProcessingReport(
            settings=NoteEventPostProcessingSettings(),
            input_event_count=invalid_count,  # type: ignore[arg-type]
            output_event_count=0,
            short_duration_removed_count=0,
            duplicate_removed_count=0,
            duplicate_group_count=0,
        )


def test_report_rejects_inconsistent_input_equation() -> None:
    with pytest.raises(InvalidNoteEventPostProcessingContractError):
        NoteEventPostProcessingReport(
            settings=NoteEventPostProcessingSettings(),
            input_event_count=3,
            output_event_count=1,
            short_duration_removed_count=1,
            duplicate_removed_count=0,
            duplicate_group_count=0,
        )


@pytest.mark.parametrize(
    ("duplicate_removed_count", "duplicate_group_count"),
    [(0, 1), (1, 0), (1, 2)],
)
def test_report_rejects_inconsistent_duplicate_groups(
    duplicate_removed_count: int,
    duplicate_group_count: int,
) -> None:
    with pytest.raises(InvalidNoteEventPostProcessingContractError):
        NoteEventPostProcessingReport(
            settings=NoteEventPostProcessingSettings(),
            input_event_count=1 + duplicate_removed_count,
            output_event_count=1,
            short_duration_removed_count=0,
            duplicate_removed_count=duplicate_removed_count,
            duplicate_group_count=duplicate_group_count,
        )


def test_report_rejects_non_settings_object() -> None:
    with pytest.raises(InvalidNoteEventPostProcessingContractError):
        NoteEventPostProcessingReport(
            settings=object(),  # type: ignore[arg-type]
            input_event_count=0,
            output_event_count=0,
            short_duration_removed_count=0,
            duplicate_removed_count=0,
            duplicate_group_count=0,
        )


def test_result_rejects_inconsistent_note_count() -> None:
    report = NoteEventPostProcessingReport(
        settings=NoteEventPostProcessingSettings(),
        input_event_count=0,
        output_event_count=0,
        short_duration_removed_count=0,
        duplicate_removed_count=0,
        duplicate_group_count=0,
    )

    with pytest.raises(InvalidNoteEventPostProcessingContractError):
        NoteEventPostProcessingResult(notes=object(), report=report)  # type: ignore[arg-type]


def test_result_accepts_empty_batch_and_matching_report() -> None:
    batch = NoteEventBatch(events=())
    report = NoteEventPostProcessingReport(
        settings=NoteEventPostProcessingSettings(),
        input_event_count=0,
        output_event_count=0,
        short_duration_removed_count=0,
        duplicate_removed_count=0,
        duplicate_group_count=0,
    )

    result = NoteEventPostProcessingResult(notes=batch, report=report)

    assert result.notes is batch
    assert result.report is report
