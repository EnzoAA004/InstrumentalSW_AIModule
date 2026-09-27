from __future__ import annotations

import io
import os
from importlib.util import find_spec
from pathlib import Path

import pytest
from tests.synthetic_audio import synthetic_saxophone_phrase_wav

from saxo_ai.application.note_event_serialization import serialize_note_event_batch
from saxo_ai.infrastructure.hf_saxophone import (
    BASELINE_PACKAGE_VERSION,
    BASELINE_SOURCE_REVISION,
    CHECKPOINT_FILENAME,
    CHECKPOINT_SHA256,
    CHECKPOINT_SIZE,
    MODEL_ID,
    MODEL_REVISION,
    BaselineExecutionDiagnostics,
    HfSaxophoneTranscriptionEngine,
)

pytestmark = [pytest.mark.integration, pytest.mark.baseline_integration]


def _baseline_available() -> bool:
    return find_spec("hf_midi_transcription") is not None


def test_real_pinned_filosax_baseline_transcribes_generated_a4(
    capsys: pytest.CaptureFixture[str],
) -> None:
    if not _baseline_available():
        reason = "hf-midi-transcription baseline extra is not installed; Python 3.11 CI requires it"
        if os.getenv("SAXO_REQUIRE_BASELINE") == "1":
            pytest.fail(reason)
        pytest.skip(reason)

    cache_root = Path(os.getenv("HF_HOME", str(Path.home() / ".cache" / "huggingface")))
    checkpoint_was_cached = (
        cache_root.exists() and next(cache_root.rglob(CHECKPOINT_FILENAME), None) is not None
    )
    diagnostics: list[BaselineExecutionDiagnostics] = []
    engine = HfSaxophoneTranscriptionEngine(diagnostics_observer=diagnostics.append)
    result = engine.transcribe(io.BytesIO(synthetic_saxophone_phrase_wav()))

    assert result.model.engine_version == BASELINE_PACKAGE_VERSION
    assert result.model.engine_source_revision == BASELINE_SOURCE_REVISION
    assert result.model.model_id == MODEL_ID
    assert result.model.model_revision == MODEL_REVISION
    assert result.model.checkpoint_filename == CHECKPOINT_FILENAME
    assert result.model.checkpoint_sha256 == CHECKPOINT_SHA256
    assert CHECKPOINT_SIZE == 99341469
    assert result.settings.sample_rate_hz == 16000
    assert result.settings.device == "cpu"
    assert result.notes.events
    assert all(0 <= event.pitch_concert_midi <= 127 for event in result.notes.events)
    assert any(65 <= event.pitch_concert_midi <= 73 for event in result.notes.events)
    assert serialize_note_event_batch(result.notes)
    assert diagnostics and diagnostics[0].event_count == len(result.notes.events)

    first_event = result.notes.events[0]
    with capsys.disabled():
        print(
            "BASELINE_DIAGNOSTICS "
            f"cache_status={'hit' if checkpoint_was_cached else 'download'} "
            f"download_seconds={diagnostics[0].checkpoint_download_seconds:.6f} "
            f"verification_seconds={diagnostics[0].checkpoint_verification_seconds:.6f} "
            f"initialization_seconds={diagnostics[0].initialization_seconds:.6f} "
            f"inference_seconds={diagnostics[0].inference_seconds:.6f} "
            f"events={diagnostics[0].event_count} "
            f"first_pitch={first_event.pitch_concert_midi} "
            f"first_onset={first_event.onset_seconds:.6f} "
            f"first_offset={first_event.offset_seconds:.6f} "
            f"first_velocity={first_event.velocity} "
            f"first_confidence={first_event.confidence:.6f}"
        )
