# NoteEvent contract — schema 1.0

## Objective

`NoteEvent` is the model-independent representation exchanged between future transcription engines and the rest of Saxo. The contract allows engines to be compared, replaced, and chained without changing musical-domain consumers.

SAX-020 defines data and JSON only. It does not define or instantiate a transcription engine.

## Traceability

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

Related functional requirement: `RF-030`. Model and checkpoint provenance from `RF-032` and the replaceable engine from `RF-033` are deliberately completed by SAX-021 rather than embedded in every event.

## Version

The only supported version is:

```text
1.0
```

Every serialized batch includes `schema_version`. Missing versions are invalid payloads. Values other than the string `"1.0"` raise `UnsupportedNoteEventSchemaVersionError`; no version coercion or best-effort migration occurs.

## Event fields

| Field | Type | Unit/meaning | Valid range |
|---|---|---|---|
| `pitch_concert_midi` | Python `int`, never `bool` | Concert-pitch MIDI note number | `0..127` |
| `onset_seconds` | finite `int` or `float`, normalized to `float` | Start time from canonical-audio origin | `>= 0.0` |
| `offset_seconds` | finite `int` or `float`, normalized to `float` | End time from canonical-audio origin | strictly greater than onset |
| `velocity` | Python `int`, never `bool` | MIDI-compatible intensity | `0..127` |
| `confidence` | finite `int` or `float`, normalized to `float` | Confidence declared by the producing engine | `0.0..1.0` |

The public names are exact. Aliases such as `pitch`, `start`, `end`, `score`, or `probability` are not accepted.

## Concert pitch

`pitch_concert_midi` records sounding concert pitch. It does not contain the written saxophone pitch. Instrument-specific written transposition belongs to SAX-030.

The contract does not store note names, frequency in hertz, pitch bend, or cent deviation.

## Temporal rules

Times use seconds from the beginning of canonical audio:

```text
onset_seconds >= 0
 offset_seconds > onset_seconds
```

A zero-duration or negative-duration event is invalid. SAX-020 does not establish a configurable minimum duration, quantize timing, infer tempo, sort events, or resolve overlaps.

`duration_seconds` is a read-only calculated property equal to `offset_seconds - onset_seconds`. It is not a dataclass field and is not serialized.

## Velocity

`velocity` is a MIDI-compatible integer intensity value. The boundaries `0` and `127` are valid. SAX-020 does not apply dynamic normalization, velocity curves, or acoustic-volume interpretation.

## Confidence

`confidence` is a finite value in the closed interval `0.0..1.0`. It is preserved exactly as a numeric declaration from the future producer and normalized to Python `float`.

It is not a boolean, a guaranteed accuracy measurement, or a filtering instruction. SAX-020 does not hide low-confidence notes or apply a threshold. Low-confidence classification belongs to SAX-023.

## Versioned batch

A `NoteEventBatch` contains:

```text
schema_version: "1.0"
events: tuple[NoteEvent, ...]
```

An empty batch is valid. Input event sequences are normalized to an immutable tuple. Every member must already be a valid `NoteEvent`.

The batch preserves the received order. It does not:

- sort chronologically;
- deduplicate identical events;
- merge events;
- reject individually valid overlaps;
- impose monophony;
- filter short notes;
- mark low confidence.

Those policies belong to later post-processing stories, principally SAX-022 and SAX-023.

## JSON representation

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

Serialization uses standard-library `json`, always emits the two root fields and exactly the five event fields, preserves event order, permits empty batches, rejects non-finite numbers, and emits no Python class names, paths, bytes, or model metadata.

The implementation produces deterministic compact JSON with sorted object keys. Consumers must not depend on whitespace or key order; they must depend on field names and values.

## Strict deserialization

The reader rejects in a controlled way:

- malformed JSON and non-finite JSON constants;
- a root that is not an object;
- missing or unknown root fields;
- absent, numeric, empty, or unsupported schema versions;
- `events` values that are not arrays;
- event entries that are not objects;
- missing or unknown event fields;
- incorrect types and values violating `NoteEvent` invariants.

No silent coercion occurs. For example, `"60"` is not converted to `60`, and `"0.5"` is not converted to `0.5`.

When an invalid event occurs inside `events`, `InvalidNoteEventPayloadError` carries `event_index` and produces a message such as:

```text
Invalid event at index 2: offset_seconds must be greater than onset_seconds
```

## Stable errors

- `InvalidNoteEventError`: a domain event or batch violates a value invariant.
- `InvalidNoteEventPayloadError`: JSON syntax or structure violates the public batch shape.
- `UnsupportedNoteEventSchemaVersionError`: a batch declares a version other than `"1.0"`.

The errors are independent of HTTP and never include complete payloads or stack traces in their messages.

## Unknown fields

Unknown root and event fields are rejected. This prevents misspellings and future metadata from being silently discarded. A future compatible schema must receive a new documented version and reader behavior.

## Deliberately deferred fields

Schema 1.0 does not include:

```text
source_model
checkpoint
model_version
written_pitch
note_name
frequency_hz
pitch_bend
cent_deviation
low_confidence
quantized_onset
quantized_offset
tempo
```

In particular, model and checkpoint provenance will be added at result or batch level by SAX-021. It is not repeated on every `NoteEvent`.

## Compatibility expected for SAX-021

A future engine adapter may produce valid `NoteEvent` objects and package them in `NoteEventBatch(schema_version="1.0")`. SAX-021 may wrap or extend result-level provenance, but it must not weaken the event invariants or change the five schema-1.0 event fields without a new schema version.
