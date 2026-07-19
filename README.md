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

Jobs are stored only in memory and begin with status `UPLOADED`. Each job includes the SHA-256 calculated from bounded upload reads. SAX-011 and SAX-012 do not connect preprocessing or validation to these endpoints.

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

`AUDIO_CONTENT_INVALID` is the stable domain failure code used only when an already accepted MP3/WAV cannot be decoded by the real FFmpeg conversion command. It is distinct from an unsupported extension and from technical failures such as unavailable FFmpeg, timeout, missing output, invalid generated output, executor failure, or destination-write failure.

On invalid content, the internal validation use case stores a new immutable `FAILED` version of the job and produces no canonical destination bytes. This capability is not exposed through HTTP yet.

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
├── api/             # Existing FastAPI transport only
├── application/     # Use cases and small ports
├── domain/          # Immutable job and canonical-audio contracts
├── infrastructure/  # SHA-256 and FFmpeg adapters
└── main.py          # Existing API composition root
```

Dependencies point inward. FastAPI does not participate in canonical conversion or validation; infrastructure owns FFmpeg, subprocess, temporary files, and WAV validation.

## Scope boundaries

The module does not connect validation to endpoints, persist audio, enforce size/duration limits, implement retries/workers/queues, download or run models, train models, generate MIDI/MusicXML, or use cloud services.
