from __future__ import annotations

from saxo_ai.domain.note_confidence import (
    ConfidenceAnnotatedNoteEvent,
    ConfidenceAnnotatedTranscriptionResult,
    LowConfidenceReport,
    LowConfidenceSettings,
)
from saxo_ai.domain.note_event_postprocessing import PostProcessedTranscriptionResult
from saxo_ai.domain.note_events import NoteEvent


def _is_low_confidence(event: NoteEvent, threshold: float) -> bool:
    return event.confidence < threshold


class MarkLowConfidenceEvents:
    """Annotate every postprocessed event without changing or removing it."""

    def __init__(self, *, settings: LowConfidenceSettings | None = None) -> None:
        self._settings = settings or LowConfidenceSettings()

    def execute(
        self,
        original: PostProcessedTranscriptionResult,
    ) -> ConfidenceAnnotatedTranscriptionResult:
        annotations = tuple(
            ConfidenceAnnotatedNoteEvent(
                event=event,
                is_low_confidence=_is_low_confidence(
                    event,
                    self._settings.low_confidence_threshold,
                ),
            )
            for event in original.notes.events
        )
        low_confidence_count = sum(annotation.is_low_confidence for annotation in annotations)
        report = LowConfidenceReport(
            settings=self._settings,
            input_event_count=len(annotations),
            low_confidence_count=low_confidence_count,
            regular_confidence_count=len(annotations) - low_confidence_count,
        )
        return ConfidenceAnnotatedTranscriptionResult(
            original=original,
            annotated_events=annotations,
            report=report,
        )
