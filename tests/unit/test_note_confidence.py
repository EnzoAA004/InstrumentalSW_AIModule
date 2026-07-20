from dataclasses import FrozenInstanceError

import pytest

from saxo_ai.domain.note_confidence import (
    CONFIDENCE_INTERPRETATION,
    DEFAULT_LOW_CONFIDENCE_THRESHOLD,
    LOW_CONFIDENCE_POLICY_VERSION,
    LOW_CONFIDENCE_VIEW_SCHEMA_VERSION,
    ConfidenceAnnotatedNoteEvent,
    InvalidLowConfidenceContractError,
    LowConfidenceReport,
    LowConfidenceSettings,
)
from saxo_ai.domain.note_events import NoteEvent


def make_event(*, confidence: float = 0.4) -> NoteEvent:
    return NoteEvent(
        pitch_concert_midi=60,
        onset_seconds=0.0,
        offset_seconds=0.5,
        velocity=100,
        confidence=confidence,
    )


def test_contract_constants_are_stable() -> None:
    assert LOW_CONFIDENCE_POLICY_VERSION == "1.0"
    assert LOW_CONFIDENCE_VIEW_SCHEMA_VERSION == "1.0"
    assert DEFAULT_LOW_CONFIDENCE_THRESHOLD == 0.50
    assert CONFIDENCE_INTERPRETATION == "model_signal_not_calibrated_accuracy"


def test_settings_defaults_are_versioned() -> None:
    settings = LowConfidenceSettings()

    assert settings.low_confidence_threshold == 0.50
    assert settings.policy_version == "1.0"


@pytest.mark.parametrize("threshold", [0, 0.0, 0.25, 0.5, 1, 1.0])
def test_settings_accept_valid_thresholds_and_normalize_to_float(threshold: int | float) -> None:
    settings = LowConfidenceSettings(low_confidence_threshold=threshold)

    assert settings.low_confidence_threshold == float(threshold)
    assert isinstance(settings.low_confidence_threshold, float)


@pytest.mark.parametrize(
    "threshold",
    [-0.001, 1.001, float("nan"), float("inf"), float("-inf"), True, False, "0.5", None],
)
def test_settings_reject_invalid_thresholds(threshold: object) -> None:
    with pytest.raises(InvalidLowConfidenceContractError):
        LowConfidenceSettings(low_confidence_threshold=threshold)  # type: ignore[arg-type]


def test_settings_reject_unsupported_policy_version() -> None:
    with pytest.raises(InvalidLowConfidenceContractError):
        LowConfidenceSettings(policy_version="2.0")


def test_settings_are_immutable() -> None:
    settings = LowConfidenceSettings()

    with pytest.raises(FrozenInstanceError):
        settings.low_confidence_threshold = 0.25  # type: ignore[misc]


def test_annotation_preserves_event_reference_and_bool_marker() -> None:
    event = make_event()

    annotation = ConfidenceAnnotatedNoteEvent(event=event, is_low_confidence=True)

    assert annotation.event is event
    assert annotation.is_low_confidence is True


def test_annotation_rejects_non_note_event() -> None:
    with pytest.raises(InvalidLowConfidenceContractError):
        ConfidenceAnnotatedNoteEvent(
            event=object(),  # type: ignore[arg-type]
            is_low_confidence=True,
        )


@pytest.mark.parametrize("marker", [0, 1, "true", None, object()])
def test_annotation_rejects_non_boolean_marker(marker: object) -> None:
    with pytest.raises(InvalidLowConfidenceContractError):
        ConfidenceAnnotatedNoteEvent(
            event=make_event(),
            is_low_confidence=marker,  # type: ignore[arg-type]
        )


def test_annotation_is_immutable() -> None:
    annotation = ConfidenceAnnotatedNoteEvent(event=make_event(), is_low_confidence=True)

    with pytest.raises(FrozenInstanceError):
        annotation.is_low_confidence = False  # type: ignore[misc]


def test_report_calculates_affected_as_marked_count() -> None:
    report = LowConfidenceReport(
        settings=LowConfidenceSettings(),
        input_event_count=3,
        low_confidence_count=2,
        regular_confidence_count=1,
    )

    assert report.affected_event_count == 2


def test_report_rejects_negative_count() -> None:
    with pytest.raises(InvalidLowConfidenceContractError):
        LowConfidenceReport(
            settings=LowConfidenceSettings(),
            input_event_count=-1,
            low_confidence_count=0,
            regular_confidence_count=0,
        )


@pytest.mark.parametrize("count", [True, 1.0, "1", None])
def test_report_rejects_non_integer_count(count: object) -> None:
    with pytest.raises(InvalidLowConfidenceContractError):
        LowConfidenceReport(
            settings=LowConfidenceSettings(),
            input_event_count=count,  # type: ignore[arg-type]
            low_confidence_count=0,
            regular_confidence_count=0,
        )


def test_report_rejects_inconsistent_count_equation() -> None:
    with pytest.raises(InvalidLowConfidenceContractError):
        LowConfidenceReport(
            settings=LowConfidenceSettings(),
            input_event_count=3,
            low_confidence_count=1,
            regular_confidence_count=1,
        )


def test_report_rejects_non_settings_object() -> None:
    with pytest.raises(InvalidLowConfidenceContractError):
        LowConfidenceReport(
            settings=object(),  # type: ignore[arg-type]
            input_event_count=0,
            low_confidence_count=0,
            regular_confidence_count=0,
        )
