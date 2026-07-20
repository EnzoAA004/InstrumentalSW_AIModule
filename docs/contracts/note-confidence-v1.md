# Note confidence review view — v1

## Objective

SAX-023 adds a deterministic output view that identifies postprocessed note events whose model-declared confidence signal is below an operational threshold. The purpose is to prioritize human review without hiding, deleting, reordering, or changing any musical event.

This contract runs after SAX-022 and is not connected to FastAPI or a frontend yet.

## Traceability

```text
SAX-023
→ configurable threshold
→ is_low_confidence marker
→ event preservation
→ versioned JSON view
→ MarkLowConfidenceEvents
→ tests/unit/test_note_confidence.py
→ tests/unit/test_transcription_confidence.py
→ tests/unit/test_note_confidence_serialization.py
```

## Versions and constants

```text
LOW_CONFIDENCE_POLICY_VERSION       1.0
LOW_CONFIDENCE_VIEW_SCHEMA_VERSION  1.0
DEFAULT_LOW_CONFIDENCE_THRESHOLD    0.50
CONFIDENCE_INTERPRETATION           model_signal_not_calibrated_accuracy
```

The policy version identifies the classification rule. The view schema version identifies the output JSON shape. They are explicit even though both currently equal `1.0`.

## Threshold rule

For effective threshold `T`:

```text
confidence < T  → is_low_confidence = true
confidence = T  → is_low_confidence = false
confidence > T  → is_low_confidence = false
```

The comparison is strictly `<`. It does not use `<=`, rounding, epsilon, `math.isclose`, calibration, ranking, or engine-specific reinterpretation.

### Boundary examples

```text
T = 0.50, confidence = 0.499999  → true
T = 0.50, confidence = 0.500000  → false
T = 0.50, confidence = 0.500001  → false
```

```text
T = 0.0  → no valid NoteEvent is marked
T = 1.0  → values below 1.0 are marked; exactly 1.0 is not marked
```

## Configuration

`LowConfidenceSettings` is frozen and slotted. `low_confidence_threshold`:

- accepts `int` or `float`;
- is normalized to `float`;
- must be finite;
- must be in the inclusive interval `0.0..1.0`;
- rejects booleans, strings, `None`, NaN, infinities, negatives, and values above one.

No environment variable is introduced in SAX-023. The settings object is injected directly into `MarkLowConfidenceEvents`.

## Meaning of confidence

Confidence is an internal signal declared by the transcription engine. It does **not** represent a calibrated probability that a note is correct and does **not** guarantee musical accuracy.

Explicitly:

```text
0.8 does not mean 80% accuracy.
```

A confidence value is not assumed comparable between different engines, checkpoints, datasets, confidence methods, instruments, or runtime revisions.

## Meaning of the marker

`is_low_confidence = true` means only:

> The event's confidence signal is below the configured operational threshold and should be prioritized for human review.

It does not mean:

- the note is incorrect;
- the note should be deleted;
- the user should ignore the note;
- the signal is a calibrated error probability;
- the event is less accurate by a known percentage.

The marker is deliberately named `is_low_confidence`, never `is_wrong` or `is_inaccurate`.

## Pipeline position

```text
TranscriptionResult
        │
        ▼
PostProcessTranscriptionEvents  (SAX-022)
        │
        ▼
PostProcessedTranscriptionResult
        │
        ▼
MarkLowConfidenceEvents         (SAX-023)
        │
        ▼
ConfidenceAnnotatedTranscriptionResult
```

SAX-023 does not classify raw adapter output. It does not repeat minimum-duration filtering or deduplication and does not execute the model.

## Domain contracts

### LowConfidenceSettings

Records the effective threshold and policy version.

### ConfidenceAnnotatedNoteEvent

```python
ConfidenceAnnotatedNoteEvent(
    event: NoteEvent,
    is_low_confidence: bool,
)
```

Invariants:

- `event` is an existing `NoteEvent`;
- the event is retained by reference;
- `is_low_confidence` is a real boolean;
- numeric `0`/`1`, strings, and truthy substitutes are rejected;
- no NoteEvent field is copied or changed.

### LowConfidenceReport

Records:

```text
settings
input_event_count
low_confidence_count
regular_confidence_count
affected_event_count
```

`affected_event_count` means marked and equals `low_confidence_count`. It never means removed.

Invariant:

```text
input_event_count
=
low_confidence_count
+
regular_confidence_count
```

Every count is a non-negative integer and booleans are rejected.

### ConfidenceAnnotatedTranscriptionResult

Contains:

```text
original          PostProcessedTranscriptionResult
annotated_events  ordered tuple of annotations
report            LowConfidenceReport
```

For every index:

```python
result.annotated_events[index].event is result.original.notes.events[index]
```

The number of annotations equals both the number of postprocessed events and the report input count.

## Absolute event preservation

For every threshold:

```text
input event count = annotation count
```

SAX-023 preserves:

- confidence `0.0`;
- confidence exactly at the threshold;
- confidence `1.0`;
- velocity `0`;
- overlapping events;
- events outside chronological order;
- every event retained by SAX-022.

No event is filtered, replaced, merged, reconstructed, or reordered.

## Provenance preservation

The result keeps `PostProcessedTranscriptionResult` as `original`, which keeps the raw `TranscriptionResult`. Therefore the following remain available without duplicated provenance strings:

- raw NoteEventBatch;
- postprocessed NoteEventBatch;
- SAX-022 report and settings;
- engine name and version;
- engine source revision;
- model ID and revision;
- checkpoint filename and SHA-256;
- inference settings;
- confidence method.

The source of truth remains the nested original contracts.

## Versioned frontend view

`serialize_confidence_annotated_result` is an output-only standard-library JSON serializer. It is deterministic and uses:

```python
json.dumps(
    document,
    sort_keys=True,
    allow_nan=False,
    separators=(",", ":"),
)
```

No deserializer is provided because this is not a trusted input contract.

### Root fields

```text
schema_version
policy_version
low_confidence_threshold
confidence_interpretation
confidence_method
summary
events
```

`confidence_method` is read from the original transcription settings, not copied into a new provenance contract.

### Summary

```text
event_count
low_confidence_count
```

### Event fields

The serializer reuses the five `NOTE_EVENT_FIELDS` and adds only:

```text
is_low_confidence
```

The original `NoteEvent` schema and serializer remain unchanged.

### Example

```json
{
  "schema_version": "1.0",
  "policy_version": "1.0",
  "low_confidence_threshold": 0.5,
  "confidence_interpretation": "model_signal_not_calibrated_accuracy",
  "confidence_method": "max_reg_onset_activation_pm2_frames",
  "summary": {
    "event_count": 2,
    "low_confidence_count": 1
  },
  "events": [
    {
      "pitch_concert_midi": 60,
      "onset_seconds": 0.0,
      "offset_seconds": 0.5,
      "velocity": 100,
      "confidence": 0.4,
      "is_low_confidence": true
    },
    {
      "pitch_concert_midi": 67,
      "onset_seconds": 0.1,
      "offset_seconds": 0.6,
      "velocity": 90,
      "confidence": 0.7,
      "is_low_confidence": false
    }
  ]
}
```

The emitted string is compact and key-sorted; the indented example is for readability only.

## Deliberately absent fields

The view does not include:

```text
is_correct
is_incorrect
accuracy
probability_correct
probability_incorrect
error_probability
is_wrong
is_inaccurate
```

It also does not embed the complete SAX-022 report.

## Complexity

`MarkLowConfidenceEvents` traverses the postprocessed events once:

```text
time:                O(n)
additional memory:   O(n)
```

It stores one lightweight annotation per event and does not copy audio, activations, tensors, checkpoints, or model output buffers.

## Relationship with SAX-022

SAX-022 decides which structurally valid events survive minimum-duration and exact-duplicate policy. SAX-023 only annotates those survivors. It does not mutate the SAX-022 policy, result, counts, order, or report.

## Future consumer

SAX-042 may consume this view to visually prioritize notes for manual review. That future integration must preserve the semantics documented here and must not present confidence as calibrated correctness.

## Limitations and future extensions

Not included in v1:

- confidence calibration;
- accuracy or correctness estimation;
- comparison between engines;
- threshold per user or saxophone type;
- environment configuration;
- confidence-based filtering or ordering;
- editing or review state;
- FastAPI or frontend wiring.

Any future calibrated interpretation, engine comparison, or policy change requires explicit evaluation, a new documented policy decision, and contract-version review.
