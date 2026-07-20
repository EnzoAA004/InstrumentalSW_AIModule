# TDD iteration 006 — SAX-013

## Scope

Implement configurable resource limits for audio ingestion and canonical conversion without beginning musical transcription. Upload size is enforced during incremental SHA-256 inspection and exposed through HTTP 413. Duration is enforced only after FFmpeg produces and the adapter semantically validates the temporary canonical WAV, before any bytes reach the caller destination.

This iteration does not implement SAX-020, `NoteEvent`, inference, audio storage, permanent canonical artifacts, queues, workers, databases, Backend, or Frontend changes.

## Traceability

```text
SAX-013
→ max_size_bytes
→ max_duration_seconds
→ HTTP 413 AUDIO_SIZE_LIMIT_EXCEEDED
→ JobFailureCode.AUDIO_DURATION_LIMIT_EXCEEDED
→ tests/unit/test_audio_limits.py
→ tests/integration/test_audio_limit_enforcement.py
```

The repository has no central traceability matrix, so the relationship is recorded here and in the pull request.

## Default limits

```text
max_size_bytes:        104857600 bytes (100 MiB)
max_duration_seconds:  900.0 seconds (15 minutes)
```

`AudioProcessingLimits` is a frozen, slotted domain value object. Size must be a positive integer. Duration must be a finite positive numeric value. Boolean values are rejected explicitly.

## Runtime configuration

The composition root loads optional overrides using only the standard library:

```text
SAXO_MAX_AUDIO_SIZE_BYTES
SAXO_MAX_AUDIO_DURATION_SECONDS
```

Missing variables preserve defaults. Invalid values fail application construction with `AudioProcessingConfigurationError`; invalid configuration is never silently replaced by defaults. Domain code does not read environment variables. Tests may inject `AudioProcessingLimits` directly into `create_app`.

## Size and duration separation

### Size

Size is known during ingestion and is enforced before job creation. The incremental hasher requests only the bytes required to decide acceptance:

```python
remaining_until_rejection = max_size_bytes - size_bytes + 1
read_size = min(chunk_size, remaining_until_rejection)
chunk = stream.read(read_size)
```

For a maximum `N`:

- `N` bytes are accepted and fully hashed;
- `N + 1` bytes raise `AudioSizeLimitExceededError`;
- no more than `N + 1` bytes are returned before rejection;
- hashing stops immediately;
- no metadata, job, `job_id`, FFmpeg call, or persisted content is produced.

Unsupported extensions still fail before any read. Empty accepted files still fail as `EmptyAudioFileError` before a job is stored.

### Duration

Duration is trusted only after reading the canonical WAV header and validating compression, sample width, sample rate, channels, and positive frame count. The FFmpeg adapter compares `frame_count / sample_rate` with the configured maximum before copying the temporary output to the caller destination.

For a maximum `D`:

- `duration == D` is accepted;
- `duration > D` raises `AudioDurationLimitExceededError`;
- the destination remains empty;
- the temporary workspace is removed;
- no `CanonicalAudioResult` or final artifact is produced.

## HTTP 413

Only upload size is connected to HTTP in this iteration. An oversized upload returns:

```json
{
  "detail": {
    "code": "AUDIO_SIZE_LIMIT_EXCEEDED",
    "message": "Audio exceeds the maximum allowed size of 104857600 bytes.",
    "max_size_bytes": 104857600
  }
}
```

The public payload intentionally omits `observed_size_bytes`, partial hashes, binary data, paths, and `job_id`.

## Duration failure model

A valid audio that exceeds duration policy is not corrupt. `ValidateTranscriptionAudio` maps only `AudioDurationLimitExceededError` to:

```text
JobStatus.FAILED
JobFailureCode.AUDIO_DURATION_LIMIT_EXCEEDED
```

The transition remains immutable and preserves job ID, filename, size, SHA-256, saxophone type, and input mode. `AUDIO_CONTENT_INVALID` remains reserved for a non-zero real FFmpeg conversion command caused by undecodable content. Technical errors remain retryable and propagate without assigning either functional code.

## RED

Tests were written and executed before production changes.

```text
python -m pytest \
  tests/unit/test_audio_limits.py \
  tests/integration/test_audio_limit_enforcement.py

collected 0 items / 2 errors
ImportError: cannot import name 'AudioDurationLimitExceededError'
ImportError: cannot import name 'AudioProcessingLimits'
RED_EXIT_CODE=2
```

The missing contracts also included `AudioSizeLimitExceededError`, runtime configuration, HTTP 413, `AUDIO_DURATION_LIMIT_EXCEEDED`, incremental `N + 1` reads, and duration enforcement before destination copying.

Remote test-only commits preceded production:

```text
4fdb955  test(SAX-013): define audio size and duration limits
ed1377f  test(SAX-013): add real FFmpeg limit contracts
```

## GREEN

The minimum implementation added immutable limits, standard-library environment loading, incremental size rejection, structured HTTP 413, duration validation before destination copying, immutable duration-failure state, and real FFmpeg boundary tests. The focused limit suite passed 38 tests locally before the complete suite was run.

## REFACTOR

- Runtime environment access is isolated in infrastructure.
- The composition root owns loading and dependency injection.
- Domain and application remain free of FastAPI and environment access.
- Size enforcement reuses the existing hashing traversal instead of adding a second read.
- Duration enforcement stays adjacent to semantic WAV validation and before output copying.
- `ValidateTranscriptionAudio` uses a shared immutable failure helper for content and duration failures.
- No diagnostic stderr, path, partial hash, or temporary artifact enters the domain.

## Exact boundary evidence

```text
Size maximum 8: accepted, complete hash, read requests [9, 1], HTTP 202.
Size 9: rejected after 9 returned bytes, unread content remains, no job, HTTP 413.
Duration 16000/16000: 1.000000 seconds, accepted, destination WAV written.
Duration 16001/16000: 1.0000625 seconds, FAILED/AUDIO_DURATION_LIMIT_EXCEEDED, destination empty, workspace removed.
```

## Partial-artifact guarantee

Size rejection occurs before any job or conversion exists. Duration rejection may occur after FFmpeg has created a temporary WAV, but only after semantic validation and before `destination.write`. The temporary workspace is context-managed and removed on success and failure. No partial temporary file is represented as a final artifact.

## Tests

The suite covers limits and environment validation, invalid startup configuration, direct `create_app` injection, exact-size hashing, early `N + 1` rejection, extension-before-read, empty-file behavior, no save on size rejection, HTTP 202/GET/health/413, distinct duration failure, real WAV boundaries, MP3 below the limit, corrupt content classification, destination emptiness, and temporary cleanup. All fixtures are generated by code.

## Local environment and exact results

```text
Python 3.13.5
ffmpeg version 7.1.3-0+deb13u1 Copyright (c) 2000-2025 the FFmpeg developers

python -m pip install -e ".[dev]"
Successfully built instrumentalsw-ai-module
Successfully installed instrumentalsw-ai-module-0.1.0

python scripts/check_quality.py
114 passed in 4.66s
481 statements, 17 missed; 100 branches, 17 partial
Total coverage: 94.15%
All checks passed!
33 files already formatted
Success: no issues found in 33 source files
Quality gate passed.

python -m pytest
114 passed in 4.38s

python -m pytest -m "not integration"
105 passed, 9 deselected in 0.41s

python -m pytest -m integration
9 passed, 105 deselected in 4.22s
skips: 0

python -m pytest --cov=saxo_ai --cov-report=term-missing --cov-report=xml
114 passed in 4.65s
Coverage XML written to file coverage.xml
Total coverage: 94.15%

python -m ruff check src tests scripts
All checks passed!

python -m ruff format --check src tests scripts
33 files already formatted

python -m mypy
Success: no issues found in 33 source files
```

## CI

The workflow keeps `SAXO_REQUIRE_FFMPEG=1` and protected check names `Python 3.11`, `Python 3.12`, and `Python 3.13`. Final remote results are recorded after the draft pull request matrix completes.

## Limitations and stories not implemented

- duration validation is intentionally not connected to FastAPI;
- no `failure_code` is added to public HTTP responses;
- no storage of original or canonical audio;
- no per-user limits, retries, queues, workers, object storage, PostgreSQL, Redis, Docker, or authentication;
- no SAX-020, `NoteEvent`, model inference, training, datasets, MIDI, or MusicXML;
- Backend and Frontend are unchanged.
