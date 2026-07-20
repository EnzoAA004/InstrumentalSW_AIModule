from __future__ import annotations

from pathlib import Path

from saxo_ai.domain.note_events import NOTE_EVENT_SCHEMA_VERSION
from saxo_ai.infrastructure.hf_saxophone import (
    BASELINE_PACKAGE_NAME,
    BASELINE_PACKAGE_VERSION,
    BASELINE_SOURCE_REVISION,
    BEGIN_MIDI_NOTE,
    CHECKPOINT_FILENAME,
    CHECKPOINT_SHA256,
    CHECKPOINT_SIZE,
    CONFIDENCE_METHOD,
    FRAMES_PER_SECOND,
    MODEL_ID,
    MODEL_REVISION,
    HfSaxophoneTranscriptionEngine,
    PinnedFiloSaxCheckpointResolver,
)
from tests.unit.hf_saxophone_fakes import (
    FakeDownloader,
    FakeRuntime,
    FakeRuntimeFactory,
    SpyStream,
    WorkspaceTracker,
    make_checkpoint,
    valid_external_output,
)


def test_pinned_constants_are_exact() -> None:
    assert BASELINE_PACKAGE_NAME == "hf-midi-transcription"
    assert BASELINE_PACKAGE_VERSION == "0.1.1"
    assert MODEL_ID == "xavriley/midi-transcription-models"
    assert MODEL_REVISION == "982ce108d7010bc3c4f36cf851caea8d4c94763d"
    assert CHECKPOINT_FILENAME == "filosax_25k.pth"
    assert CHECKPOINT_SHA256 == "448cf2c8ea6d4b77f7435f5b9a496211ea60300c5c17fa9c754da764f75f3a6a"
    assert CHECKPOINT_SIZE == 99341469
    assert FRAMES_PER_SECOND == 100
    assert BEGIN_MIDI_NOTE == 21
    assert CONFIDENCE_METHOD == "max_reg_onset_activation_pm2_frames"


def test_non_seekable_stream_is_copied_in_bounded_blocks_and_result_has_provenance(
    tmp_path: Path,
) -> None:
    path, digest = make_checkpoint(tmp_path)
    resolver = PinnedFiloSaxCheckpointResolver(
        downloader=FakeDownloader(path), expected_sha256=digest, expected_size=path.stat().st_size
    )
    runtime = FakeRuntime(valid_external_output())
    factory = FakeRuntimeFactory(runtime)
    source = SpyStream(b"RIFF" + b"x" * 150000)
    engine = HfSaxophoneTranscriptionEngine(
        checkpoint_resolver=resolver,
        runtime_factory=factory,
        copy_chunk_size=65536,
    )
    result = engine.transcribe(source)
    assert source.requests and all(request == 65536 for request in source.requests)
    assert result.model.engine_name == BASELINE_PACKAGE_NAME
    assert result.model.engine_version == BASELINE_PACKAGE_VERSION
    assert result.model.engine_source_revision == BASELINE_SOURCE_REVISION
    assert result.model.model_id == MODEL_ID
    assert result.model.model_revision == MODEL_REVISION
    assert result.model.checkpoint_filename == CHECKPOINT_FILENAME
    assert result.model.checkpoint_sha256 == digest
    assert result.settings.sample_rate_hz == 16000
    assert result.settings.device == "cpu"
    assert result.settings.confidence_method == CONFIDENCE_METHOD
    assert result.notes.schema_version == NOTE_EVENT_SCHEMA_VERSION
    assert len(result.notes.events) == 1
    note = result.notes.events[0]
    assert note.pitch_concert_midi == 69
    assert note.onset_seconds == 0.0
    assert note.offset_seconds == 0.5
    assert note.velocity == 100
    assert note.confidence == 0.92


def test_adapter_sorts_deterministically_but_preserves_duplicates_and_overlaps(
    tmp_path: Path,
) -> None:
    path, digest = make_checkpoint(tmp_path)
    events: list[dict[str, object]] = [
        {"onset_time": 1.0, "offset_time": 1.5, "midi_note": 70, "velocity": 80},
        {"onset_time": 0.0, "offset_time": 0.75, "midi_note": 69, "velocity": 100},
        {"onset_time": 0.0, "offset_time": 0.75, "midi_note": 69, "velocity": 100},
        {"onset_time": 0.5, "offset_time": 1.25, "midi_note": 67, "velocity": 90},
    ]
    matrix = [[0.5 for _ in range(88)] for _ in range(160)]
    engine = HfSaxophoneTranscriptionEngine(
        checkpoint_resolver=PinnedFiloSaxCheckpointResolver(
            downloader=FakeDownloader(path),
            expected_sha256=digest,
            expected_size=path.stat().st_size,
        ),
        runtime_factory=FakeRuntimeFactory(
            FakeRuntime(valid_external_output(events=events, onset_matrix=matrix))
        ),
    )
    notes = engine.transcribe(SpyStream(b"wav")).notes.events
    assert [
        (n.onset_seconds, n.pitch_concert_midi, n.offset_seconds, n.velocity) for n in notes
    ] == [
        (0.0, 69, 0.75, 100),
        (0.0, 69, 0.75, 100),
        (0.5, 67, 1.25, 90),
        (1.0, 70, 1.5, 80),
    ]


def test_workspace_is_cleaned_after_success(tmp_path: Path) -> None:
    path, digest = make_checkpoint(tmp_path)
    tracker = WorkspaceTracker()
    engine = HfSaxophoneTranscriptionEngine(
        checkpoint_resolver=PinnedFiloSaxCheckpointResolver(
            downloader=FakeDownloader(path),
            expected_sha256=digest,
            expected_size=path.stat().st_size,
        ),
        runtime_factory=FakeRuntimeFactory(),
        temporary_directory_factory=tracker,
    )
    engine.transcribe(SpyStream(b"wav"))
    tracker.assert_cleaned()


def test_contract_boundaries_do_not_connect_fastapi_or_change_note_event_schema() -> None:
    root = Path(__file__).resolve().parents[2]
    domain = (root / "src/saxo_ai/domain/transcription.py").read_text(encoding="utf-8").lower()
    application = (
        (root / "src/saxo_ai/application/transcription.py").read_text(encoding="utf-8").lower()
    )
    errors = (
        (root / "src/saxo_ai/application/transcription_errors.py")
        .read_text(encoding="utf-8")
        .lower()
    )
    for source in (domain, application, errors):
        for forbidden in ("torch", "huggingface", "hf_midi_transcription", "fastapi"):
            assert forbidden not in source

    main = (root / "src/saxo_ai/main.py").read_text(encoding="utf-8")
    routes = (root / "src/saxo_ai/api/routes.py").read_text(encoding="utf-8")
    assert "HfSaxophoneTranscriptionEngine" not in main
    assert "TranscribeCanonicalAudio" not in main
    assert "HfSaxophoneTranscriptionEngine" not in routes
    assert "TranscribeCanonicalAudio" not in routes
    assert NOTE_EVENT_SCHEMA_VERSION == "1.0"
