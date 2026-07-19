# TDD iteration 005 — SAX-012

## Scope

Implement an internal application capability that distinguishes accepted MP3/WAV content that FFmpeg cannot decode from unsupported extensions and technical conversion failures. Only a non-zero result from the real content conversion command creates the functional failed-job state.

This iteration does not connect validation to FastAPI, does not add HTTP behavior, does not persist audio, and does not implement SAX-013.

## Traceability

```text
SAX-012
→ detection of non-decodable accepted audio content
→ JobStatus.FAILED
→ JobFailureCode.AUDIO_CONTENT_INVALID
→ tests/unit/test_audio_validation.py
→ tests/integration/test_corrupt_audio_detection.py
```

The repository has no central traceability matrix, so this relationship is recorded here and in the pull request.

## Exact definition of invalid audio

Content is invalid only when all conditions are true:

1. its filename extension was already accepted as `.mp3` or `.wav`;
2. the real canonical conversion command is invoked;
3. FFmpeg exits non-zero because it cannot interpret or decode the supplied content.

The stable functional code is the domain enum value:

```text
AUDIO_CONTENT_INVALID
```

FFmpeg stderr is diagnostic only and never becomes a functional code.

## Differentiation

### Unsupported extension

A name such as `audio.flac` produces `UnsupportedAudioFormatError`. `CreateTranscriptionJob` rejects it before consuming the stream, creating a job, or involving FFmpeg.

### Invalid supported content

An existing `.mp3` or `.wav` job whose trusted source cannot be decoded becomes a new immutable `FAILED` job with `failure_code=AUDIO_CONTENT_INVALID`. No canonical result is returned and the destination remains empty.

### Technical failure

Unavailable FFmpeg, timeout, non-zero `ffmpeg -version`, executor failure, missing output, invalid generated WAV, and destination-write failure propagate unchanged. The job remains `UPLOADED`, retains `failure_code=None`, and remains retryable.

## State model

`JobStatus` contains `UPLOADED` and `FAILED`. `JobFailureCode` currently contains only `AUDIO_CONTENT_INVALID`.

`TranscriptionJob` remains frozen and enforces:

- `FAILED` requires a failure code;
- non-failed jobs reject a failure code;
- `mark_failed(...)` returns a new object;
- filename, size, hash, saxophone type, input mode, and job ID are preserved;
- no stderr, path, stack trace, timestamp, retry counter, or state history enters the entity.

## Architecture

```text
trusted BinaryStream + caller BinaryDestination
                  │
                  ▼
       ValidateTranscriptionAudio
          │                  │
          ▼                  ▼
TranscriptionJobRepository   CanonicalAudioConverter
          │                  │
          │                  ▼
          │       FfmpegCanonicalAudioConverter
          │                  │
          └──── FAILED only on AudioContentInvalidError
```

The use case obtains the job, constructs `OriginalAudioReference` from filename/size/SHA-256, invokes canonical conversion, and translates only `AudioContentInvalidError` into the stable failed state. Future orchestration may retrieve the trusted source from private storage; object storage is outside this story.

## RED

Tests were published before production changes.

```text
python -m pytest \
  tests/unit/test_audio_validation.py \
  tests/integration/test_corrupt_audio_detection.py \
  tests/unit/test_audio_preprocessing.py

collected 0 items / 3 errors
ModuleNotFoundError: No module named 'saxo_ai.application.audio_validation'
ImportError: cannot import name 'AudioContentInvalidError'
RED_EXIT_CODE=2
```

The missing behavior also included `JobStatus.FAILED`, `JobFailureCode`, the immutable transition, and the validation use case.

Remote test-only commits preceded production:

```text
7850562  test(SAX-012): define invalid audio failure behavior
c9ca45e  test(SAX-012): add real corrupt audio contracts
```

## GREEN

The minimum implementation added:

- immutable failed-job state and invariants;
- `AudioContentInvalidError` only for non-zero real conversion commands;
- `TranscriptionAudioValidationError` containing `job_id` and stable failure code;
- `ValidateTranscriptionAudio` orchestration;
- real corrupt and valid WAV integration paths.

The focused GREEN suite passed 29 tests.

## REFACTOR

- version-command failures remain technical `FfmpegConversionError` values;
- all non-content technical errors propagate without repository updates;
- destination and executor failures are covered explicitly;
- output is copied only after FFmpeg success and semantic WAV validation;
- no stderr, path, binary data, or infrastructure detail enters the job;
- API routes, schemas, and composition root remain disconnected and unchanged.

## Fixtures

### Corrupt

```text
filename: corrupt.wav
content: b"these bytes are not a wav file"
```

FFmpeg attempts real conversion and returns non-zero. The adapter raises `AudioContentInvalidError`; the use case persists `FAILED/AUDIO_CONTENT_INVALID`; the stable application error is raised; destination length remains zero; tracked temporary workspaces no longer exist after failure.

### Valid

A one-second 440 Hz WAV is generated with `wave`, `math`, and `struct`. Validation returns a canonical 16 kHz mono PCM16 WAV, preserves the original reference, leaves the job `UPLOADED`, and keeps `failure_code=None`.

## Partial-artifact guarantee

The converter copies to the caller destination only after conversion success, output existence, and semantic WAV validation. For invalid content, `destination.write` is not invoked. Temporary files live inside `TemporaryDirectory` and are removed on both success and failure.

## Local environment

```text
Python 3.13.5
ffmpeg version 7.1.3-0+deb13u1 Copyright (c) 2000-2025 the FFmpeg developers
```

## Exact local results

```text
python -m pip install -e ".[dev]"
Successfully built instrumentalsw-ai-module
Successfully installed instrumentalsw-ai-module-0.1.0

python scripts/check_quality.py
73 passed in 3.24s
391 statements, 5 missed; 74 branches, 5 partial
Total coverage: 97.85%
All checks passed!
30 files already formatted
Success: no issues found in 30 source files
Quality gate passed.

python -m pytest
73 passed in 3.38s

python -m pytest -m "not integration"
68 passed, 5 deselected in 0.36s

python -m pytest -m integration
5 passed, 68 deselected in 2.62s
skips: 0

python -m pytest --cov=saxo_ai --cov-report=term-missing --cov-report=xml
73 passed in 4.08s
Coverage XML written to file coverage.xml
Total coverage: 97.85%

python -m ruff check src tests scripts
All checks passed!

python -m ruff format --check src tests scripts
30 files already formatted

python -m mypy
Success: no issues found in 30 source files
```

## CI

The workflow retains `SAXO_REQUIRE_FFMPEG=1` and the protected check names:

```text
Python 3.11
Python 3.12
Python 3.13
```

Remote results will be recorded after the draft pull request workflow completes. The matrix must run the real corrupt and valid fixtures; no third-party FFmpeg action is used.

## Limitations and not implemented

- no FastAPI integration or new HTTP status code;
- no original/canonical permanent storage or object storage;
- no retries, workers, queues, or orchestration states;
- no `VALID`, `PREPROCESSING`, or `PREPROCESSED` state;
- no size or duration limits and no SAX-013;
- no database, Redis, Docker, amplitude normalization, models, inference, training, datasets, MIDI, or MusicXML;
- Backend and Frontend are unchanged.
