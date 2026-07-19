# TDD iteration 003 — SAX-010

## Scope

Calculate and expose a SHA-256 digest for each uploaded audio stream while preserving the current in-memory job lifecycle. This iteration does not decode, convert, persist, deduplicate, or inspect the musical validity of audio.

## Design decisions

- The API knows FastAPI `UploadFile` and passes its binary file object to application code.
- `CreateTranscriptionJob` depends on the generic `BinaryStream` and `AudioContentHasher` application ports.
- `Sha256AudioContentHasher` lives in infrastructure and is the only component that imports `hashlib`.
- `AudioContentMetadata` and `TranscriptionJob` are immutable domain values.
- The POST endpoint is synchronous, so FastAPI executes the blocking stream loop in its worker thread pool rather than on an async event loop.
- Extension validation occurs before the stream is inspected.

## RED

Tests were committed before production changes.

Command:

```text
python -m pytest tests/unit/test_audio_hashing.py
```

Exact result:

```text
collected 9 items
9 failed in 0.28s
RED_EXIT_CODE=1
```

Expected failures included:

```text
ModuleNotFoundError: No module named 'saxo_ai.infrastructure.hashing'
KeyError: 'audio_sha256'
create_transcription remained an AsyncFunctionDef with an awaited read
```

## GREEN

The minimum implementation added:

- SHA-256 through the Python standard-library `hashlib` module;
- one-pass bounded stream processing;
- simultaneous digest and byte-count calculation;
- `audio_sha256` storage in `TranscriptionJob`;
- `audio_sha256` in POST and GET responses;
- rejection of empty streams before repository save;
- rejection of unsupported extensions before stream consumption.

## REFACTOR

- The binary stream and hasher are application protocols.
- FastAPI does not appear in application or domain.
- `hashlib` does not appear in domain.
- Hash and size are calculated together; the stream is traversed once.
- The metadata result and job remain frozen dataclasses.
- Tests verify that no `seek`, `tell`, path access, or unbounded `read()` is required.

## Tests created

- known SHA-256 vector for `abc`;
- identical content with different names;
- different content with the same name;
- lowercase 64-character hexadecimal contract;
- bounded reads on a non-seekable spy stream;
- size from the same returned chunks;
- empty stream without repository save;
- unsupported extension without stream consumption;
- POST/GET response contract;
- synchronous route without awaited upload reads;
- non-positive chunk-size validation;
- architectural dependency boundaries.

## Block size and memory behavior

The production constant is:

```text
DEFAULT_CHUNK_SIZE = 64 * 1024
```

Each iteration invokes `stream.read(65536)`. The returned chunk is immediately fed to the digest and its length is added to the total. No operation requests the full file, the stream does not need to be seekable, and audio bytes are not retained or persisted after each chunk is processed.

## Local verification

```text
python -m pip install -e ".[dev]"                         PASS
python scripts/check_quality.py                            39 passed; quality gate passed
python -m pytest                                           39 passed
python -m pytest --cov=saxo_ai --cov-report=term-missing --cov-report=xml
                                                         100% (152 statements, 12 branches)
python -m ruff check src tests scripts                      All checks passed
python -m ruff format --check src tests scripts             22 files already formatted
python -m mypy                                             Success: no issues found in 22 source files
GET /health                                                HTTP 200 {"status":"ok"}
POST synthetic abc.wav                                     HTTP 202; expected SHA-256
GET created job                                            HTTP 200; same SHA-256
```

## CI

GitHub Actions results for Python 3.11, 3.12, and 3.13 will be recorded in the pull request after the draft PR workflow completes.

## Limitations and stories not implemented

- No comparison or automatic deduplication by hash.
- Equal hashes do not merge jobs; every accepted POST creates a distinct job.
- No audio content persistence.
- No SAX-011 canonical conversion or FFmpeg.
- No corruption detection, size/duration limits, databases, queues, object storage, models, datasets, MIDI, or MusicXML.
- Backend and Frontend are unchanged.
