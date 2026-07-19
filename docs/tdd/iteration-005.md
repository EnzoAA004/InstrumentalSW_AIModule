# TDD iteration 005 — SAX-012

## Scope

Detect supported MP3/WAV content that FFmpeg cannot decode, persist an immutable failed-job state, and expose a stable internal application error. The capability remains internal and is not connected to FastAPI.

## Traceability

```text
SAX-012
→ detection of non-decodable content
→ JobStatus.FAILED
→ JobFailureCode.AUDIO_CONTENT_INVALID
→ tests/unit/test_audio_validation.py
→ tests/integration/test_corrupt_audio_detection.py
```

## Exact definition

Content is invalid only when its `.mp3` or `.wav` extension was previously accepted and the real FFmpeg conversion command returns a non-zero status because it cannot decode the supplied bytes.

- Unsupported extension: `UnsupportedAudioFormatError`; no job, no read, no FFmpeg.
- Invalid supported content: existing job becomes `FAILED` with `AUDIO_CONTENT_INVALID`.
- Technical failure: original error propagates; job remains `UPLOADED` and retryable.

FFmpeg stderr and temporary paths are diagnostic details and are never stored in the domain entity.

## Domain model

`JobStatus` now includes `FAILED`. `JobFailureCode` contains the single stable value `AUDIO_CONTENT_INVALID`. `TranscriptionJob.failure_code` defaults to `None`.

Invariants:

- `FAILED` requires a failure code;
- non-failed jobs reject a failure code;
- jobs remain frozen dataclasses;
- `mark_failed` returns a new object and preserves identity and input metadata.

## Architecture

```text
trusted BinaryStream + caller BinaryDestination
                     ↓
       ValidateTranscriptionAudio
           ↓                 ↓
TranscriptionJobRepository   CanonicalAudioConverter
                                  ↓
                    FfmpegCanonicalAudioConverter
```

The use case creates `OriginalAudioReference` from the stored filename, size, and SHA-256. Future orchestration will retrieve the trusted source from private storage; object storage is outside this story.

## RED

Tests were committed before production changes.

```text
python -m pytest tests/unit/test_audio_validation.py \
  tests/integration/test_corrupt_audio_detection.py

collected 0 items / 2 errors
ModuleNotFoundError: No module named 'saxo_ai.application.audio_validation'
RED_EXIT_CODE=2
```

The failures also represented missing `JobStatus.FAILED`, `JobFailureCode`, immutable transition, content-specific FFmpeg error, and validation use case.

## GREEN

The minimum implementation added:

- immutable failed-job domain state;
- `AudioContentInvalidError` only for non-zero conversion commands;
- `TranscriptionAudioValidationError` with `job_id` and stable failure code;
- `ValidateTranscriptionAudio` orchestration;
- real corrupt and valid WAV integration tests.

## REFACTOR

- Version-command failures remain `FfmpegConversionError` and are not content failures.
- Technical failures propagate without repository updates.
- The destination is written only after FFmpeg succeeds and WAV validation passes.
- No stderr, path, binary data, or infrastructure detail enters the job entity.
- API routes, schemas, and composition root remain disconnected.

## Fixtures

### Corrupt

`corrupt.wav` is generated in memory from arbitrary non-WAV bytes. FFmpeg attempts conversion, the use case persists `FAILED/AUDIO_CONTENT_INVALID`, destination length remains zero, and tracked temporary workspaces no longer exist after the error.

### Valid

A one-second A4 WAV is generated with `wave`, `math`, and `struct`. Conversion returns a canonical 16 kHz mono PCM16 WAV, preserves the original reference, leaves the job `UPLOADED`, and keeps `failure_code=None`.

## Partial-artifact guarantee

The converter copies to the caller destination only after a successful conversion and semantic WAV validation. Invalid content therefore cannot produce a final artifact; `destination.write` is not invoked and temporary files are context-managed.

## Local results

Environment: Python 3.13.5.

```text
python -m pip install -e ".[dev]"                         PASS
python -m pytest -m "not integration"                    68 passed, 5 deselected
python -m pytest -m integration                          5 passed, 68 deselected, 0 skipped
python -m pytest                                         73 passed
python -m pytest --cov=saxo_ai --cov-report=term-missing --cov-report=xml
                                                        73 passed; 97.85%
python -m ruff check src tests scripts                   All checks passed
python -m ruff format --check src tests scripts          30 files already formatted
python -m mypy                                          Success: no issues in 30 source files
python scripts/check_quality.py                          Quality gate passed
```

FFmpeg:

```text
ffmpeg version 7.1.3-0+deb13u1 Copyright (c) 2000-2025 the FFmpeg developers
```

## CI

The existing workflow keeps `SAXO_REQUIRE_FFMPEG=1` and the protected job names `Python 3.11`, `Python 3.12`, and `Python 3.13`. Final remote results are recorded in the PR after the draft workflow completes.

## Limitations and not implemented

- No HTTP integration or new HTTP status codes.
- No SAX-013 size or duration limits.
- No original/canonical permanent storage, object storage, database, queues, workers, retries, or state history.
- No `VALID`, `PREPROCESSING`, or `PREPROCESSED` state.
- No amplitude normalization, models, inference, training, datasets, MIDI, or MusicXML.
- Backend and Frontend are unchanged.
