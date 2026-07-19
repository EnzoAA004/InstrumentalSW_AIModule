# InstrumentalSW AI Module

Python/FastAPI module for InstrumentalSW (Saxo), developed through reproducible TDD iterations.

## Requirements

- Python `>=3.11,<3.14`
- `pip`
- FFmpeg for real canonical-audio integration tests

Verify the external tool with:

```bash
ffmpeg -version
```

The unit suite does not require FFmpeg. Real conversion tests are marked `integration`; when FFmpeg is unavailable locally they are skipped with a clear reason. CI installs FFmpeg explicitly and sets `SAXO_REQUIRE_FFMPEG=1`, so absence of the tool fails the workflow.

## Install

```bash
python -m pip install -e ".[dev]"
```

## Run locally

```bash
python -m uvicorn saxo_ai.main:app --reload
```

## Minimal API

- `GET /health`
- `POST /api/v1/transcriptions`
- `GET /api/v1/transcriptions/{job_id}`

Jobs are stored only in memory and begin with status `UPLOADED`. Each job includes `audio_sha256`, the lowercase 64-character SHA-256 digest calculated from the uploaded content in bounded 64 KiB reads. Uploaded bytes are not persisted and matching hashes do not deduplicate jobs.

SAX-011 does not change these endpoints or invoke preprocessing from job creation.

## Canonical audio capability

The internal canonical converter accepts a generic non-seekable binary source and writes to a destination supplied by the caller. Its default representation is:

```text
container:                 wav
codec:                     pcm_s16le
sample_rate_hz:            16000
channels:                  1
sample_width_bits:         16
amplitude_normalization:   none
preprocessing schema:      1.0
```

`sample_rate_hz` is configurable with positive integer values and `channels` supports `1` or `2`. Container, codec, sample width, and the explicit absence of amplitude normalization remain fixed in SAX-011.

The FFmpeg adapter materializes the input and output inside an automatically cleaned temporary workspace, copies both directions in bounded 64 KiB blocks, validates the result semantically with Python's `wave` module, and returns metadata without exposing temporary paths. It does not provide loudness, peak, LUFS, or volume normalization.

## Quality and tests

Run the same complete quality gate used by GitHub Actions on Windows PowerShell or Unix:

```bash
python scripts/check_quality.py
```

The command runs, in order:

1. pytest with statement and branch coverage, XML output, and a 90% minimum threshold;
2. Ruff lint;
3. Ruff format in check-only mode;
4. mypy with the project's strict configuration.

Useful focused commands:

```bash
# Tests that do not require the external FFmpeg executable
python -m pytest -m "not integration"

# Real WAV and MP3 conversion through FFmpeg
python -m pytest -m integration
```

GitHub Actions runs the full command on pull requests targeting `main`, pushes to `main`, and manual dispatches. The matrix verifies Python 3.11, 3.12, and 3.13. The runner stops at the first failed control and returns that tool's non-zero exit code.

## Architecture

```text
src/saxo_ai/
├── api/             # Existing FastAPI transport only
├── application/     # Use cases and small ports
├── domain/          # Immutable job and canonical-audio contracts
├── infrastructure/  # SHA-256 and FFmpeg adapters
└── main.py          # Existing API composition root
```

Dependencies point inward. FastAPI does not participate in canonical conversion; application and domain do not import FastAPI, and only infrastructure imports `subprocess`, `tempfile`, and FFmpeg-specific concerns.

## Scope boundaries

The current module does not connect canonical conversion to transcription jobs, classify corrupt audio, change job states, persist original or converted audio, enforce duration/size limits, download or run models, train models, generate MIDI/MusicXML, or use cloud services. Those capabilities belong to later stories.
