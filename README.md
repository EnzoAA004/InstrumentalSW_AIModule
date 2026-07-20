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

The complete schema is documented in [`docs/contracts/note-event-v1.md`](docs/contracts/note-event-v1.md). No transcription engine, model, checkpoint, or inference integration exists yet; those belong to SAX-021.

## Quality and tests

```bash
python scripts/check_quality.py
python -m pytest -m "not integration"
python -m pytest -m integration
```

The quality command runs pytest with statement/branch coverage and a 90% threshold, Ruff lint, Ruff format check, and strict mypy. GitHub Actions runs it for Python 3.11, 3.12, and 3.13. The runner stops at the first failed control and returns a non-zero exit code.

## Architecture

```text
src/saxo_ai/
├── api/             # FastAPI transport and HTTP error translation
├── application/     # Use cases, ports, stable errors, and JSON contracts
├── domain/          # Immutable jobs, audio policy, and NoteEvent contract
├── infrastructure/  # Environment, SHA-256, FFmpeg, and in-memory repository
└── main.py          # Composition root and dependency injection
```

Dependencies point inward. FastAPI does not appear in domain or application. Environment variables are loaded only at the infrastructure/composition boundary. FFmpeg, subprocess, and temporary files remain infrastructure concerns.

## Scope boundaries

The module does not connect duration validation to endpoints, persist audio, implement retries/workers/queues, download or run models, train models, generate MIDI/MusicXML, or use cloud services. SAX-020 defines data contracts only; SAX-021 and musical inference have not started.
