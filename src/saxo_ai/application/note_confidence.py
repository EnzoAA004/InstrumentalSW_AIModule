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
        annotations: list[ConfidenceAnnotatedNoteEvent] = []
        low_confidence_count = 0
        for event in original.notes.events:
            is_low_confidence = _is_low_confidence(
                event,
                self._settings.low_confidence_threshold,
            )
            annotations.append(
                ConfidenceAnnotatedNoteEvent(
                    event=event,
                    is_low_confidence=is_low_confidence,
                )
            )
            if is_low_confidence:
                low_confidence_count += 1

        annotated_events = tuple(annotations)
        report = LowConfidenceReport(
            settings=self._settings,
            input_event_count=len(annotated_events),
            low_confidence_count=low_confidence_count,
            regular_confidence_count=len(annotated_events) - low_confidence_count,
        )
        return ConfidenceAnnotatedTranscriptionResult(
            original=original,
            annotated_events=annotated_events,
            report=report,
        )
