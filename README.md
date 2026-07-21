# InstrumentalSW AI Module

Python/FastAPI module for InstrumentalSW (Saxo), developed through reproducible TDD iterations.

## Requirements

- Python `>=3.11,<3.14`
- `pip`
- FFmpeg for real canonical-audio integration tests

Verify FFmpeg with:

```bash
ffmpeg -version
```

Unit tests do not require FFmpeg. Real conversion tests are marked `integration`; locally they skip with a clear reason when FFmpeg is absent. CI installs FFmpeg and sets `SAXO_REQUIRE_FFMPEG=1`, so absence fails the workflow.

## Install and run

```bash
python -m pip install -e ".[dev]"
python -m uvicorn saxo_ai.main:app --reload
```

## Minimal API

- `GET /health`
- `POST /api/v1/transcriptions`
- `GET /api/v1/transcriptions/{job_id}`

Jobs are stored only in memory and begin with status `UPLOADED`. Each job includes the SHA-256 calculated from bounded upload reads. SAX-013 rejects oversized uploads during that same traversal before a job is created. Canonical content and duration validation remain disconnected from these endpoints.

## Canonical audio capability

The internal converter accepts a generic non-seekable source and writes to a caller-provided destination. Its default representation is:

```text
container:                 wav
codec:                     pcm_s16le
sample_rate_hz:            16000
channels:                  1
sample_width_bits:         16
amplitude_normalization:   none
preprocessing schema:      1.0
```

Input and output are copied in bounded 64 KiB blocks through an automatically cleaned temporary workspace. The WAV result is validated semantically with Python's `wave` module.

## Invalid audio content

`AUDIO_CONTENT_INVALID` is the stable domain failure code used only when an already accepted MP3/WAV cannot be decoded by the real FFmpeg conversion command. It is distinct from an unsupported extension and technical infrastructure failures.

On invalid content, the internal validation use case stores a new immutable `FAILED` version of the job and produces no canonical destination bytes. This capability is not exposed through HTTP yet.

## Audio processing limits

Default limits are:

```text
max_size_bytes:        104857600 bytes (100 MiB)
max_duration_seconds:  900.0 seconds (15 minutes)
```

Override them at application startup with:

```text
SAXO_MAX_AUDIO_SIZE_BYTES
SAXO_MAX_AUDIO_DURATION_SECONDS
```

Invalid values fail startup instead of silently using defaults. Tests may inject `AudioProcessingLimits` directly into `create_app`.

An upload above the size limit stops after at most `maximum + 1` returned bytes and responds with HTTP 413 and code `AUDIO_SIZE_LIMIT_EXCEEDED`; no job is created. A semantically valid canonical WAV above the duration limit becomes an internal failed job with `AUDIO_DURATION_LIMIT_EXCEEDED`. Duration validation is not connected to HTTP yet.

## Versioned NoteEvent contract

SAX-020 defines a model-independent `NoteEvent` and ordered `NoteEventBatch` with current schema version `"1.0"`. The contract uses concert-pitch MIDI, onset/offset seconds, MIDI-compatible velocity, and confidence, with strict standard-library JSON round trips.

The complete schema is documented in [`docs/contracts/note-event-v1.md`](docs/contracts/note-event-v1.md).

## Deterministic NoteEvent postprocessing

SAX-022 adds the internal `PostProcessTranscriptionEvents` use case. Its immutable policy defaults to a minimum duration of `0.030` seconds, removes only events strictly shorter than that boundary, and reduces exact duplicates identified by concert pitch plus exact onset/offset times. The retained representative is selected by confidence, then velocity, then first appearance.

A no-op returns the original `NoteEventBatch` object. The report remains separate from NoteEvent JSON schema `1.0`. See [`docs/contracts/note-event-postprocessing-v1.md`](docs/contracts/note-event-postprocessing-v1.md).

## Low-confidence review view

SAX-023 adds the internal `MarkLowConfidenceEvents` use case and a versioned JSON review view. The initial configurable threshold is `0.50`; an event is marked only when `confidence < threshold`. Every postprocessed note remains present with its original object reference and order.

Confidence is an engine signal, not calibrated accuracy: `0.8` does not mean 80% accuracy. The view adds only `is_low_confidence` and is documented in [`docs/contracts/note-confidence-v1.md`](docs/contracts/note-confidence-v1.md). It is not connected to FastAPI or a frontend yet.

## Written saxophone pitch

SAX-030 adds the internal `TransposeWrittenPitchEvents` use case. It preserves every concert-pitch `NoteEvent` and derives a separate integer `written_pitch_midi` through the existing instrument rule:

```text
soprano Bb   +2
alto Eb      +9
tenor Bb    +14
baritone Eb +21
```

The scalar function rejects invalid concert pitches, invalid saxophone types, and any attempted written pitch outside `0..127`; it never clips or changes octave. The complete immutable contract, atomic batch behavior, and exact MIDI boundaries are documented in [`docs/contracts/written-pitch-v1.md`](docs/contracts/written-pitch-v1.md).

SAX-030 itself creates no file. SAX-031 consumes its immutable result while preserving both sounding concert pitch and written-pitch provenance.

## Deterministic concert-pitch MIDI export

SAX-031 adds the internal `ExportWrittenPitchToMidi` use case behind a `MidiFileEncoder` application port. The production adapter uses pinned `mido==1.3.3` to generate and parse a deterministic Standard MIDI File entirely in memory.

```text
file type:             1
ticks per beat:        480
tracks:                2
channel:               0
pitch representation:  concert
default tempo:         120 BPM
```

The playback note always comes from the original `pitch_concert_midi`; `written_pitch_midi` remains available only through provenance for notation stories. Source velocity zero becomes note-on velocity one and is reported. A positive duration that rounds to zero receives one technical tick without changing the source seconds. At the same tick, note-off is ordered before note-on, and all emitted delta times are non-negative.

The adapter validates its own bytes by reopening them with Mido. Integration tests also check the binary header, open a temporary `.mid` file, preserve overlaps, and verify an empty batch. The artifact contains bytes, media type, extension, size, and application-calculated SHA-256; it contains no path and is not persisted.

The complete contract is documented in [`docs/contracts/midi-export-v1.md`](docs/contracts/midi-export-v1.md). This capability is not connected to FastAPI, job state, storage, Backend, or Frontend.

## Tempo resolution

SAX-032 adds a replaceable `TempoEstimator` port and a deterministic standard-library baseline based only on exact note onsets. It calculates consecutive inter-onset intervals, converts them to BPM candidates, selects their median, resolves configured-range octave equivalents, and reports IOI consensus.

```text
estimator:             median_onset_interval
minimum BPM:           40.0
maximum BPM:          240.0
minimum intervals:      2
consensus tolerance:    0.08
```

Confidence equals `inlier intervals / total intervals`; it is not calibrated accuracy, so `0.8` does not mean 80% tempo accuracy. Exact duplicate onsets are removed only inside estimation and never from the original result.

Manual tempo works even when automatic estimation is unavailable. Every explicit override creates a new immutable revision while preserving the original and automatic estimate by reference. `ExportTempoResolvedMidi` regenerates MIDI through the existing SAX-031 exporter and retains the exact tempo revision used.

The complete contract is documented in [`docs/contracts/tempo-resolution-v1.md`](docs/contracts/tempo-resolution-v1.md). SAX-032 does not analyze audio, estimate meter, quantize rhythm, create MusicXML, or connect the flow to FastAPI.

## Optional FiloSax baseline

SAX-021 provides an internal, replaceable FiloSax audio-to-note baseline behind
`TranscriptionEngine` and `TranscribeCanonicalAudio`. Python 3.11 is the validated inference
environment.

Install the optional model stack with the controlled installer:

```bash
python scripts/install_baseline.py
```

The installer uses no pip cache, force-installs both Git distributions from exact commits with
`--no-deps`, and verifies their PEP 610 `direct_url.json` metadata:

```text
hf-midi-transcription
  version: 0.1.1
  source:  96f6797881e9497cbfc8f8e5deccea9c1f2f7adc

piano-transcription-inference
  version: 0.1.0
  source:  7568dc7f78b625e40cf9776e2806d164006610e3
```

The model is not downloaded during installation. It is resolved only when inference or the real
integration test runs. Reproducibility also fixes the Hugging Face model revision and verifies the
checkpoint filename, byte size, and SHA-256 before loading.

See [`docs/baselines/hf-saxophone-v1.md`](docs/baselines/hf-saxophone-v1.md) for the distinction
between package version, source revision, model revision, and checkpoint checksum.

The baseline is not instantiated by the FastAPI composition root and is not connected to any
endpoint.

## Quality and tests

```bash
python scripts/check_quality.py
python -m pytest
python -m pytest -m "not integration"
python -m pytest -m integration
python -m pytest -m midi_integration
python -m pytest -m baseline_integration
python -m pytest --cov=saxo_ai --cov-report=term-missing --cov-report=xml
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
python -m mypy
```

The quality command runs pytest with statement/branch coverage and a 90% threshold, Ruff lint, Ruff format check, and strict mypy. GitHub Actions runs it for Python 3.11, 3.12, and 3.13. The runner stops at the first failed control and returns a non-zero exit code.

Real `midi_integration` tests run on all three supported Python versions. The real FiloSax `baseline_integration` is required only on Python 3.11; on Python 3.12 and 3.13 it skips with an explicit reason while the full core, FFmpeg, and MIDI integration suites continue to run.

## Architecture

```text
src/saxo_ai/
├── api/             # FastAPI transport and HTTP error translation
├── application/     # Use cases, ports, stable errors, JSON, and artifact metadata
├── domain/          # Immutable jobs, audio policy, note, pitch, tempo, and result contracts
├── infrastructure/  # Environment, hashing, FFmpeg, repositories, model, MIDI, and tempo adapters
└── main.py          # Composition root and dependency injection
```

Dependencies point inward. FastAPI does not appear in domain or application. Environment variables are loaded only at the infrastructure/composition boundary. FFmpeg, Hugging Face, PyTorch, Mido, subprocesses, and temporary files remain infrastructure concerns. Content hashing is calculated outside domain.

## Scope boundaries

The module does not connect duration validation, model inference, NoteEvent postprocessing, confidence annotations, written-pitch transposition, MIDI export, or tempo resolution to endpoints; persist audio or MIDI; implement retries/workers/queues; train models; generate MusicXML or a rendered score; or use product cloud storage. SAX-032 does not implement rhythmic quantization, notation, audio beat tracking, playback, Backend, or Frontend behavior.
