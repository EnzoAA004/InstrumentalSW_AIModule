from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from saxo_ai.application.midi_export import ExportWrittenPitchToMidi
from saxo_ai.domain.midi_export import MidiExportResult, MidiExportSettings
from saxo_ai.domain.tempo import (
    AutomaticTempoEstimate,
    InvalidTempoEstimateError,
    InvalidTempoResolutionError,
    InvalidTempoSettingsError,
    TempoEstimationSettings,
    TempoEstimationUnavailableError,
    TempoResolution,
    TempoSelectionSource,
    normalize_positive_bpm,
)
from saxo_ai.domain.written_pitch import WrittenPitchTranscriptionResult


class TempoEstimatorError(RuntimeError):
    """Raised when a replaceable tempo estimator fails unexpectedly."""


@runtime_checkable
class TempoEstimator(Protocol):
    def estimate(
        self,
        original: WrittenPitchTranscriptionResult,
        settings: TempoEstimationSettings,
    ) -> AutomaticTempoEstimate: ...


@dataclass(frozen=True, slots=True)
class TempoResolvedMidiResult:
    tempo: TempoResolution
    midi: MidiExportResult

    def __post_init__(self) -> None:
        if not isinstance(self.tempo, TempoResolution):
            raise InvalidTempoResolutionError("tempo must be a TempoResolution")
        if not isinstance(self.midi, MidiExportResult):
            raise InvalidTempoResolutionError("midi must be a MidiExportResult")
        if self.midi.original is not self.tempo.original:
            raise InvalidTempoResolutionError(
                "MIDI output must preserve the tempo resolution original reference"
            )
        if self.midi.report.settings.tempo_bpm != self.tempo.effective_tempo_bpm:
            raise InvalidTempoResolutionError("MIDI settings must match the effective tempo")


class EstimateTranscriptionTempo:
    def __init__(self, estimator: TempoEstimator) -> None:
        if not isinstance(estimator, TempoEstimator):
            raise TypeError("estimator must implement TempoEstimator")
        self._estimator = estimator

    def execute(
        self,
        original: WrittenPitchTranscriptionResult,
        settings: TempoEstimationSettings,
    ) -> TempoResolution:
        if not isinstance(original, WrittenPitchTranscriptionResult):
            raise InvalidTempoEstimateError("original must be a WrittenPitchTranscriptionResult")
        if not isinstance(settings, TempoEstimationSettings):
            raise InvalidTempoSettingsError("settings must be TempoEstimationSettings")
        try:
            estimate = self._estimator.estimate(original, settings)
        except (
            InvalidTempoEstimateError,
            InvalidTempoSettingsError,
            TempoEstimationUnavailableError,
            TempoEstimatorError,
        ):
            raise
        except Exception as error:
            raise TempoEstimatorError("Tempo estimation failed.") from error
        if not isinstance(estimate, AutomaticTempoEstimate):
            raise InvalidTempoEstimateError("estimator must return AutomaticTempoEstimate")
        return TempoResolution(
            original=original,
            automatic_estimate=estimate,
            manual_tempo_bpm=None,
            effective_tempo_bpm=estimate.tempo_bpm,
            source=TempoSelectionSource.AUTOMATIC,
            revision=1,
        )


class ConfigureManualTempo:
    def execute(
        self,
        original: WrittenPitchTranscriptionResult,
        manual_tempo_bpm: object,
    ) -> TempoResolution:
        if not isinstance(original, WrittenPitchTranscriptionResult):
            raise InvalidTempoResolutionError("original must be a WrittenPitchTranscriptionResult")
        tempo = normalize_positive_bpm(
            manual_tempo_bpm,
            field_name="manual_tempo_bpm",
        )
        return TempoResolution(
            original=original,
            automatic_estimate=None,
            manual_tempo_bpm=tempo,
            effective_tempo_bpm=tempo,
            source=TempoSelectionSource.MANUAL,
            revision=1,
        )


class OverrideEstimatedTempo:
    def execute(
        self,
        previous: TempoResolution,
        manual_tempo_bpm: object,
    ) -> TempoResolution:
        if not isinstance(previous, TempoResolution):
            raise InvalidTempoResolutionError("previous must be a TempoResolution")
        tempo = normalize_positive_bpm(
            manual_tempo_bpm,
            field_name="manual_tempo_bpm",
        )
        return TempoResolution(
            original=previous.original,
            automatic_estimate=previous.automatic_estimate,
            manual_tempo_bpm=tempo,
            effective_tempo_bpm=tempo,
            source=TempoSelectionSource.MANUAL,
            revision=previous.revision + 1,
        )


class ExportTempoResolvedMidi:
    def __init__(self, exporter: ExportWrittenPitchToMidi) -> None:
        if not isinstance(exporter, ExportWrittenPitchToMidi):
            raise TypeError("exporter must be ExportWrittenPitchToMidi")
        self._exporter = exporter

    def execute(self, tempo: TempoResolution) -> TempoResolvedMidiResult:
        if not isinstance(tempo, TempoResolution):
            raise InvalidTempoResolutionError("tempo must be a TempoResolution")
        midi = self._exporter.execute(
            tempo.original,
            MidiExportSettings(tempo_bpm=tempo.effective_tempo_bpm),
        )
        return TempoResolvedMidiResult(tempo=tempo, midi=midi)
