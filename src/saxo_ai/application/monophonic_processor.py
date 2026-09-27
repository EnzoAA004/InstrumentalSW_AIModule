from __future__ import annotations

from io import BytesIO

from saxo_ai.application.errors import (
    AudioContentInvalidError,
    AudioDurationLimitExceededError,
)
from saxo_ai.application.midi_export import ExportWrittenPitchToMidi, MidiFileEncoder
from saxo_ai.application.musicxml_export import (
    ExportQuantizedRhythmToMusicXml,
    MusicXmlEncoder,
    MusicXmlReader,
)
from saxo_ai.application.note_confidence import MarkLowConfidenceEvents
from saxo_ai.application.note_event_postprocessing import PostProcessTranscriptionEvents
from saxo_ai.application.ports import CanonicalAudioConverter
from saxo_ai.application.processing import TerminalProcessingError
from saxo_ai.application.revision_artifacts import RegisterRevisionArtifacts
from saxo_ai.application.rhythm_quantization import QuantizeMonophonicRhythm
from saxo_ai.application.score_rendering import (
    InvalidScoreRendererOutputError,
    RenderMusicXmlToSvg,
    ScoreRenderer,
    ScoreRenderingError,
)
from saxo_ai.application.tempo_resolution import (
    ConfigureManualTempo,
    EstimateTranscriptionTempo,
    TempoEstimator,
)
from saxo_ai.application.transcription import TranscribeCanonicalAudio, TranscriptionEngine
from saxo_ai.application.transcription_review import RegisterTranscriptionReview
from saxo_ai.application.written_pitch import TransposeWrittenPitchEvents
from saxo_ai.domain.audio import CanonicalAudioSettings, OriginalAudioReference
from saxo_ai.domain.midi_export import MidiExportSettings
from saxo_ai.domain.models import JobFailureCode, TranscriptionJob
from saxo_ai.domain.musicxml_export import MusicXmlExportSettings
from saxo_ai.domain.revision_artifacts import (
    ArtifactType,
    RevisionArtifact,
    RevisionArtifactBundle,
    RevisionArtifactDescriptor,
)
from saxo_ai.domain.rhythm_quantization import RhythmQuantizationSettings
from saxo_ai.domain.score_rendering import ScoreRenderResult, ScoreRenderSettings
from saxo_ai.domain.tempo import TempoEstimationSettings, TempoEstimationUnavailableError


class MonophonicTranscriptionProcessor:
    """Compose the existing solo-saxophone pipeline for one claimed transcription job."""

    def __init__(
        self,
        *,
        canonical_converter: CanonicalAudioConverter,
        transcription_engine: TranscriptionEngine,
        tempo_estimator: TempoEstimator,
        midi_encoder: MidiFileEncoder,
        musicxml_encoder: MusicXmlEncoder,
        musicxml_reader: MusicXmlReader,
        score_renderer: ScoreRenderer,
        register_review: RegisterTranscriptionReview,
        register_artifacts: RegisterRevisionArtifacts,
        fallback_tempo_bpm: float = 120.0,
        canonical_settings: CanonicalAudioSettings | None = None,
        tempo_settings: TempoEstimationSettings | None = None,
        rhythm_settings: RhythmQuantizationSettings | None = None,
        musicxml_settings: MusicXmlExportSettings | None = None,
        score_settings: ScoreRenderSettings | None = None,
    ) -> None:
        self._canonical_converter = canonical_converter
        self._transcribe = TranscribeCanonicalAudio(transcription_engine)
        self._postprocess = PostProcessTranscriptionEvents()
        self._confidence = MarkLowConfidenceEvents()
        self._transpose = TransposeWrittenPitchEvents()
        self._estimate_tempo = EstimateTranscriptionTempo(tempo_estimator)
        self._manual_tempo = ConfigureManualTempo()
        self._quantize = QuantizeMonophonicRhythm()
        self._midi = ExportWrittenPitchToMidi(midi_encoder)
        self._musicxml = ExportQuantizedRhythmToMusicXml(musicxml_encoder, musicxml_reader)
        self._render = RenderMusicXmlToSvg(score_renderer)
        self._register_review = register_review
        self._register_artifacts = register_artifacts
        self._fallback_tempo_bpm = fallback_tempo_bpm
        self._canonical_settings = canonical_settings or CanonicalAudioSettings()
        self._tempo_settings = tempo_settings or TempoEstimationSettings()
        self._rhythm_settings = rhythm_settings or RhythmQuantizationSettings()
        self._musicxml_settings = musicxml_settings or MusicXmlExportSettings()
        self._score_settings = score_settings or ScoreRenderSettings()

    def process(self, job: TranscriptionJob, source: bytes) -> None:
        canonical = BytesIO()
        original = OriginalAudioReference(
            filename=job.filename,
            size_bytes=job.size_bytes,
            audio_sha256=job.audio_sha256,
        )
        try:
            self._canonical_converter.convert(
                source=BytesIO(source),
                destination=canonical,
                settings=self._canonical_settings,
                original=original,
            )
        except AudioContentInvalidError as error:
            raise TerminalProcessingError(JobFailureCode.AUDIO_CONTENT_INVALID) from error
        except AudioDurationLimitExceededError as error:
            raise TerminalProcessingError(
                JobFailureCode.AUDIO_DURATION_LIMIT_EXCEEDED
            ) from error

        raw = self._transcribe.execute(BytesIO(canonical.getvalue()))
        processed = self._postprocess.execute(raw)
        confidence = self._confidence.execute(processed)
        written = self._transpose.execute(confidence, job.saxophone_type)
        try:
            tempo = self._estimate_tempo.execute(written, self._tempo_settings)
        except TempoEstimationUnavailableError:
            tempo = self._manual_tempo.execute(written, self._fallback_tempo_bpm)

        quantized = self._quantize.execute(tempo, self._rhythm_settings)
        midi = self._midi.execute(
            written,
            MidiExportSettings(tempo_bpm=tempo.effective_tempo_bpm),
        )
        musicxml = self._musicxml.execute(quantized, self._musicxml_settings)

        rendered: ScoreRenderResult | None
        try:
            rendered = self._render.execute(musicxml, self._score_settings)
        except (ScoreRenderingError, InvalidScoreRendererOutputError):
            rendered = None

        bundle = _revision_zero_bundle(
            job=job,
            midi_content=midi.artifact.content,
            midi_media_type=midi.artifact.media_type,
            midi_extension=midi.artifact.file_extension,
            midi_sha256=midi.artifact.sha256,
            musicxml_content=musicxml.artifact.content,
            musicxml_media_type=musicxml.artifact.media_type,
            musicxml_extension=musicxml.artifact.file_extension,
            musicxml_sha256=musicxml.artifact.sha256,
            rendered=rendered,
        )
        self._register_review.execute(job.job_id, written)
        self._register_artifacts.execute(bundle)


def _revision_zero_bundle(
    *,
    job: TranscriptionJob,
    midi_content: bytes,
    midi_media_type: str,
    midi_extension: str,
    midi_sha256: str,
    musicxml_content: bytes,
    musicxml_media_type: str,
    musicxml_extension: str,
    musicxml_sha256: str,
    rendered: ScoreRenderResult | None,
) -> RevisionArtifactBundle:
    revision = 0
    artifacts = [
        _artifact(
            artifact_id="midi",
            artifact_type=ArtifactType.MIDI,
            filename=f"transcription-r{revision}{midi_extension}",
            media_type=midi_media_type,
            extension=midi_extension,
            content=midi_content,
            sha256=midi_sha256,
            order=0,
        ),
        _artifact(
            artifact_id="musicxml",
            artifact_type=ArtifactType.MUSICXML,
            filename=f"transcription-r{revision}{musicxml_extension}",
            media_type=musicxml_media_type,
            extension=musicxml_extension,
            content=musicxml_content,
            sha256=musicxml_sha256,
            order=1,
        ),
    ]
    if rendered is not None:
        artifacts.extend(
            _artifact(
                artifact_id=f"svg-page-{page.page_number:03d}",
                artifact_type=ArtifactType.SVG,
                filename=(
                    f"transcription-r{revision}-page-{page.page_number:03d}"
                    f"{page.file_extension}"
                ),
                media_type=page.media_type,
                extension=page.file_extension,
                content=page.content,
                sha256=page.sha256,
                order=index,
            )
            for index, page in enumerate(rendered.pages, start=2)
        )
    return RevisionArtifactBundle(
        job_id=job.job_id,
        revision_number=revision,
        artifacts=tuple(artifacts),
    )


def _artifact(
    *,
    artifact_id: str,
    artifact_type: ArtifactType,
    filename: str,
    media_type: str,
    extension: str,
    content: bytes,
    sha256: str,
    order: int,
) -> RevisionArtifact:
    descriptor = RevisionArtifactDescriptor(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        filename=filename,
        media_type=media_type,
        extension=extension,
        size_bytes=len(content),
        sha256=sha256,
        order=order,
    )
    return RevisionArtifact(descriptor=descriptor, content=content)
