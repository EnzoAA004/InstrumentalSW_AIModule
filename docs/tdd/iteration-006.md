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

The minimum implementation added:

- immutable `AudioProcessingLimits`;
- standard-library environment loading;
- incremental size rejection at `N + 1`;
- structured HTTP 413;
- duration validation before destination copying;
- immutable duration-failure state;
- real FFmpeg boundary tests.

The focused limit suite passed 38 tests locally before the complete suite was run.

## REFACTOR

- Runtime environment access is isolated in infrastructure.
- The composition root owns loading and dependency injection.
- Domain and application remain free of FastAPI and environment access.
- Size enforcement reuses the existing hashing traversal instead of adding a second read.
- Duration enforcement stays adjacent to semantic WAV validation and before output copying.
- `ValidateTranscriptionAudio` uses a shared immutable failure helper for content and duration failures.
- No diagnostic stderr, path, partial hash, or temporary artifact enters the domain.

## Exact boundary evidence

### Size maximum 8 bytes

```text
content: b"12345678"
result: accepted
size_bytes: 8
SHA-256: complete and correct
read requests: [9, 1]
HTTP: 202
```

### One byte over size

```text
content begins with 9 bytes and has unread remaining content
maximum: 8
returned before failure: 9 bytes
observed_size_bytes: 9
remaining stream: not consumed
job saved: no
HTTP: 413 AUDIO_SIZE_LIMIT_EXCEEDED
```

### Duration exactly 1 second

```text
sample_rate: 16000
frames: 16000
duration: 1.000000 seconds
result: accepted
job: UPLOADED, failure_code=None
destination: canonical RIFF/WAV bytes
```

### One frame over duration

```text
sample_rate: 16000
frames: 16001
duration: 1.0000625 seconds
result: rejected
job: FAILED/AUDIO_DURATION_LIMIT_EXCEEDED
destination bytes: 0
temporary workspace: removed
```

## Partial-artifact guarantee

Size rejection occurs before any job or conversion exists. Duration rejection may occur after FFmpeg has created a temporary WAV, but only after semantic validation and before `destination.write`. The temporary workspace is context-managed and removed on success and failure. No partial temporary file is represented as a final artifact.

## Tests

The suite covers:

- default, custom, invalid, boolean, NaN, and infinite limits;
- missing, valid, and invalid environment values;
- invalid startup configuration;
- direct `create_app` injection;
- exact-size hashing and early `N + 1` rejection;
- extension-before-read and empty-file behavior;
- no repository save on size rejection;
- HTTP 202, GET, health, and structured HTTP 413 contracts;
- distinct duration failure state;
- real WAV exact boundary and one-frame-over boundary;
- real MP3 below the duration limit;
- corrupt content retaining `AUDIO_CONTENT_INVALID`;
- zero destination bytes and temporary cleanup.

All fixtures are generated by code and no audio files are stored in the repository.

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

The workflow keeps `SAXO_REQUIRE_FFMPEG=1` and protected check names:

```text
Python 3.11
Python 3.12
Python 3.13
```

Final clean workflow run:

```text
Quality #32
run ID: 29710128026
Python 3.11: success
Python 3.12: success
Python 3.13: success
```

Every job completed checkout, Python setup, FFmpeg installation, editable project installation, and the shared quality gate successfully. The real WAV boundary, MP3, and corrupt-content integrations executed with `SAXO_REQUIRE_FFMPEG=1`.

## Limitations and stories not implemented

- duration validation is intentionally not connected to FastAPI;
- no `failure_code` is added to public HTTP responses;
- no storage of original or canonical audio;
- no size/duration policy per user or paid plan;
- no retries, queues, workers, object storage, PostgreSQL, Redis, Docker, or authentication;
- no SAX-020, `NoteEvent`, model inference, training, datasets, MIDI, or MusicXML;
- Backend and Frontend are unchanged.
