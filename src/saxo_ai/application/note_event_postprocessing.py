from __future__ import annotations

from saxo_ai.domain.note_event_postprocessing import (
    NoteEventPostProcessingReport,
    NoteEventPostProcessingSettings,
    PostProcessedTranscriptionResult,
)
from saxo_ai.domain.note_events import NoteEvent, NoteEventBatch
from saxo_ai.domain.transcription import TranscriptionResult

DuplicateKey = tuple[int, float, float]


def _duplicate_key(event: NoteEvent) -> DuplicateKey:
    return (event.pitch_concert_midi, event.onset_seconds, event.offset_seconds)


def _candidate_is_preferred(candidate: NoteEvent, current: NoteEvent) -> bool:
    return (candidate.confidence, candidate.velocity) > (current.confidence, current.velocity)


class PostProcessTranscriptionEvents:
    """Apply deterministic duration and exact-duplicate policy to a transcription result."""

    def __init__(
        self,
        *,
        settings: NoteEventPostProcessingSettings | None = None,
    ) -> None:
        self._settings = settings or NoteEventPostProcessingSettings()

    def execute(self, original: TranscriptionResult) -> PostProcessedTranscriptionResult:
        surviving_events: list[NoteEvent] = []
        short_duration_removed_count = 0
        for event in original.notes.events:
            if event.duration_seconds < self._settings.minimum_duration_seconds:
                short_duration_removed_count += 1
            else:
                surviving_events.append(event)

        output_events: list[NoteEvent] = []
        slots: dict[DuplicateKey, int] = {}
        duplicate_keys: set[DuplicateKey] = set()
        duplicate_removed_count = 0

        for event in surviving_events:
            key = _duplicate_key(event)
            output_index = slots.get(key)
            if output_index is None:
                slots[key] = len(output_events)
                output_events.append(event)
                continue

            duplicate_removed_count += 1
            duplicate_keys.add(key)
            current = output_events[output_index]
            if _candidate_is_preferred(event, current):
                output_events[output_index] = event

        changed = short_duration_removed_count > 0 or duplicate_removed_count > 0
        notes = (
            NoteEventBatch(
                events=tuple(output_events),
                schema_version=original.notes.schema_version,
            )
            if changed
            else original.notes
        )
        report = NoteEventPostProcessingReport(
            settings=self._settings,
            input_event_count=len(original.notes.events),
            output_event_count=len(notes.events),
            short_duration_removed_count=short_duration_removed_count,
            duplicate_removed_count=duplicate_removed_count,
            duplicate_group_count=len(duplicate_keys),
        )
        return PostProcessedTranscriptionResult(original=original, notes=notes, report=report)
