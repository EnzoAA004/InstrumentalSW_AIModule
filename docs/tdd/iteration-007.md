# TDD iteration 007 — SAX-020

## Scope

Define the model-independent, immutable `NoteEvent` value, the versioned `NoteEventBatch`, and strict standard-library JSON serialization/deserialization.

This iteration contains no audio handling, FFmpeg integration, FastAPI change, persistence, model adapter, inference, MIDI, or MusicXML.

## Story and traceability

```text
SAX-020
→ NoteEvent
→ NoteEventBatch schema 1.0
→ pitch_concert_midi
→ onset_seconds
→ offset_seconds
→ velocity
→ confidence
→ tests/unit/test_note_event.py
→ tests/unit/test_note_event_serialization.py
```

SAX-020 satisfies the event-contract portion of `RF-030`. Model/checkpoint provenance and an interchangeable engine are deferred to SAX-021.

## Acceptance criteria

- immutable, slotted `NoteEvent` with exactly five public fields;
- concert MIDI pitch and velocity restricted to integer `0..127`, excluding booleans;
- finite numeric onset `>= 0`, normalized to float;
- finite numeric offset strictly greater than onset, normalized to float;
- finite confidence in `0.0..1.0`, normalized to float;
- immutable schema-`1.0` batch, including an empty batch;
- deterministic strict JSON round trip;
- order, duplicates, and valid overlaps preserved;
- malformed structures, unknown fields, invalid values, and unsupported versions rejected;
- no model, audio, API, or infrastructure integration.

## Decision about `source_model`

The conceptual documentation previously listed `source_model` beside event fields. SAX-020 deliberately does not place it on `NoteEvent`.

SAX-021 is responsible for recording model and checkpoint provenance at result or batch level. This avoids repeating the same model identifier on every event and keeps the event reusable across adapters. Schema 1.0 therefore contains only the five musical/event values.

## Architecture

```text
src/saxo_ai/domain/note_events.py
  ├── NoteEvent
  ├── NoteEventBatch
  ├── schema and field constants
  └── domain errors and invariants

src/saxo_ai/application/note_event_serialization.py
  ├── serialize_note_event_batch
  ├── deserialize_note_event_batch
  └── strict payload error
```

The deserializer validates JSON shape and then constructs `NoteEvent`, reusing domain invariants instead of duplicating them. API, composition root, infrastructure, and existing audio code are unchanged.

## RED

The tests were created, executed, committed locally, and published remotely before production modules.

Remote test-only commits:

```text
2a7b450  test(SAX-020): define immutable NoteEvent contract
8bcd8e7  test(SAX-020): define strict NoteEvent JSON contract
```

Exact RED execution:

```text
python -m pytest \
  tests/unit/test_note_event.py \
  tests/unit/test_note_event_serialization.py

collected 0 items / 2 errors
ModuleNotFoundError: No module named 'saxo_ai.domain.note_events'
ModuleNotFoundError: No module named 'saxo_ai.application.note_event_serialization'
RED_EXIT_CODE=2
```

The missing behavior included `NoteEvent`, `NoteEventBatch`, the schema version and field constants, stable errors, and both JSON functions.

## GREEN

The minimum implementation added:

- strict MIDI-compatible integer validation;
- finite numeric normalization for times and confidence;
- immutable `NoteEvent` and batch;
- schema version `"1.0"`;
- strict root and event shape validation;
- deterministic JSON serialization;
- error indexing for entries in `events`.

Focused result:

```text
86 passed
```

## REFACTOR

- `NOTE_EVENT_FIELDS` is the single public field-name source for serialization and structure checks;
- the deserializer delegates value invariants to the domain constructor;
- event-index context is added without embedding payloads;
- event order is never sorted or filtered;
- input sequences are copied into an immutable tuple;
- runtime type annotations were clarified without weakening strict tests;
- no dependency or engine abstraction was introduced.

## Domain invariants

### `pitch_concert_midi`

Valid: `0`, `60`, `127`.

Invalid: `-1`, `128`, `60.0`, `True`, `"60"`.

### `onset_seconds`

Valid: `0`, `0.0`, and finite positive numerics; stored as float.

Invalid: negative, NaN, positive/negative infinity, bool, string, `None`.

### `offset_seconds`

Must be finite numeric and strictly greater than onset. Equality and lower values are invalid. Stored as float.

### `velocity`

Valid integer range: `0..127`, excluding bool.

### `confidence`

Valid finite numeric range: `0.0..1.0`, including integer boundaries; stored as float. No threshold is applied.

## Batch and sequence behavior

- empty `events=()` is valid;
- sequences normalize to tuple;
- received order is preserved, including non-chronological order;
- duplicate values remain duplicated and deserialize to separate immutable instances;
- individually valid overlaps remain accepted;
- no monophony, sorting, merging, filtering, quantization, or confidence marking occurs.

## JSON schema

```json
{
  "schema_version": "1.0",
  "events": [
    {
      "pitch_concert_midi": 60,
      "onset_seconds": 0.0,
      "offset_seconds": 0.5,
      "velocity": 100,
      "confidence": 0.92
    }
  ]
}
```

`duration_seconds` is a read-only calculated property and is not serialized. Model, checkpoint, written pitch, note name, frequency, low-confidence, and quantized fields are absent.

## Stable errors

- `InvalidNoteEventError` for domain values and batch members;
- `InvalidNoteEventPayloadError` for malformed or structurally invalid JSON;
- `UnsupportedNoteEventSchemaVersionError` for anything other than string `"1.0"`.

Errors occurring inside `events` contain the event index. The original domain error remains available as `__cause__` without copying the complete payload into the message.

## Boundary and invalid tests

The new unit suite covers:

- pitch and velocity at `0` and `127`;
- onset at zero;
- confidence at zero and one;
- all specified wrong types, booleans, ranges, NaN, and infinities;
- offset equality and reverse timing;
- frozen/slots behavior and exact dataclass fields;
- empty and sequence-normalized batches;
- version missing, empty, numeric, and unknown;
- malformed JSON and non-object roots;
- non-list `events` and non-object events;
- required and unknown fields;
- no coercion;
- round trip, order, duplicates, and overlaps;
- dependency and no-engine architecture boundaries.

## Exact local results

```text
Python 3.13.5
ffmpeg version 7.1.3-0+deb13u1 Copyright (c) 2000-2025 the FFmpeg developers

python -m pip install -e ".[dev]"
Successfully built instrumentalsw-ai-module
Successfully installed instrumentalsw-ai-module-0.1.0

Focused new tests:
86 passed

python scripts/check_quality.py
200 passed in 4.98s
609 statements, 18 missed; 140 branches, 18 partial
Total coverage: 95.19%
All checks passed!
37 files already formatted
Success: no issues found in 37 source files
Quality gate passed.

python -m pytest
200 passed in 4.75s

python -m pytest -m "not integration"
191 passed, 9 deselected in 0.50s

python -m pytest -m integration
9 passed, 191 deselected in 4.62s
skips: 0

python -m pytest --cov=saxo_ai --cov-report=term-missing --cov-report=xml
200 passed in 5.22s
Total coverage: 95.19%

python -m ruff check src tests scripts
All checks passed!

python -m ruff format --check src tests scripts
37 files already formatted

python -m mypy
Success: no issues found in 37 source files
```

## CI

The existing workflow remains unchanged with `SAXO_REQUIRE_FFMPEG=1` and protected check names:

```text
Python 3.11
Python 3.12
Python 3.13
```

Final remote results will be recorded after the draft pull request matrix completes.

## Coverage

Total production coverage is `95.19%`, above the required `90%`. The new note-event domain module is fully covered; strict serialization is `98%` covered.

## Limitations and stories not implemented

- no SAX-021 or `TranscriptionEngine`;
- no Basic Pitch, CREPE, Hugging Face model, checkpoint, or inference;
- no model provenance yet;
- no audio input or FFmpeg use from the contract;
- no event deduplication, merging, minimum duration, confidence threshold, low-confidence flag, or quantization;
- no written transposition, pitch bend, tempo, MIDI, or MusicXML;
- no new endpoints, job transitions, or persistence;
- Backend and Frontend are unchanged.
