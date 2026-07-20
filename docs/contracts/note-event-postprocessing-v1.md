# NoteEvent postprocessing contract — policy 1.0

## Purpose

SAX-022 defines deterministic, model-independent postprocessing for a validated `NoteEventBatch` produced by a `TranscriptionResult`. It removes events shorter than a configurable minimum and exact duplicate estimates while preserving original objects, producer provenance, and schema `1.0`.

This contract is internal to domain and application code. It is not connected to FastAPI, jobs, persistence, FiloSax internals, or SAX-023 confidence classification.

## Traceability

```text
SAX-022
→ minimum-duration filtering
→ exact deduplication
→ affected-event report
→ PostProcessTranscriptionEvents
→ tests/unit/test_note_event_postprocessing.py
→ tests/unit/test_transcription_postprocessing.py
```

## Policy identity

```text
policy version:       1.0
duplicate policy:     same_pitch_exact_interval_keep_highest_confidence
minimum duration:     0.030 seconds
```

`NoteEventPostProcessingSettings` is frozen and injected directly into the use case. No environment variable exists in this version. The minimum accepts finite `int` or `float` values greater than or equal to zero, normalizes them to `float`, rejects booleans and non-numeric values, and treats `0.0` as disabling duration filtering.

## Meaning of invalid in SAX-022

`NoteEvent` already validates MIDI pitch, timing, velocity, and confidence. SAX-022 neither accepts nor repairs structurally invalid objects and does not catch `InvalidNoteEventError`.

Within this policy, an event is removable only when:

1. its valid duration is shorter than the configured minimum; or
2. it is an exact duplicate of another surviving event.

## Duration comparison

The use case reads `event.duration_seconds` and performs no rounding:

```text
duration < minimum  → remove
duration = minimum  → keep
duration > minimum  → keep
```

With the default `0.030`, an event ending at `0.029999` from onset `0.0` is removed, while an event ending at exactly `0.030` is retained.

## Exact duplicate identity

Two events are duplicates only when all members of this key are exactly equal:

```python
(
    event.pitch_concert_midi,
    event.onset_seconds,
    event.offset_seconds,
)
```

`velocity` and `confidence` are excluded from identity because they are competing estimates of the same musical event. No epsilon, rounding, `math.isclose`, quantization, temporal window, overlap ratio, or intersection-over-union is used. Even a minimal timing difference produces a distinct event.

## Representative selection

One existing `NoteEvent` object is retained for each duplicate group. The priority is:

1. greater `confidence`;
2. on confidence tie, greater `velocity`;
3. on complete tie, first appearance in the original batch.

The policy never constructs a merged event and never averages confidence or velocity, widens intervals, or combines fields.

## Phase order

Processing is strictly:

```text
1. remove events shorter than the minimum
2. deduplicate exact keys among survivors
```

A short event cannot participate in duplicate counting. Every removed input event contributes to exactly one removal counter.

## Output order

Each duplicate group occupies the logical position of its first surviving appearance. If a later duplicate wins the tie-breaker, that complete later object replaces the representative in the first group's slot. Independent events keep their relative input order. The policy does not sort chronologically.

Example:

```text
input:
  C4 [0.00, 0.50], confidence 0.40
  G4 [0.10, 0.60], confidence 0.70
  C4 [0.00, 0.50], confidence 0.80

output:
  C4 [0.00, 0.50], confidence 0.80
  G4 [0.10, 0.60], confidence 0.70

report:
  input = 3
  output = 2
  duplicates removed = 1
  duplicate groups = 1
  affected = 1
```

## Result contracts

`NoteEventPostProcessingResult` contains a processed `NoteEventBatch` and report. `PostProcessedTranscriptionResult` additionally contains the exact original `TranscriptionResult` object:

```text
original.notes     raw NoteEventBatch
original.model     producer/model/checkpoint provenance
original.settings  inference settings
notes              processed NoteEventBatch
report             policy and counters
```

Provenance is not copied into duplicate strings. The source of truth remains `original.model` and `original.settings`.

## Report counters and invariants

The report records:

- policy version;
- minimum duration;
- duplicate policy;
- input event count;
- output event count;
- short-duration removed count;
- duplicate removed count;
- duplicate group count;
- total affected count.

Required equations:

```text
input = output + short-duration removed + duplicate removed
affected = short-duration removed + duplicate removed
```

All counters are non-negative integers. When no duplicate is removed, duplicate groups must be zero. Otherwise:

```text
1 <= duplicate groups <= duplicate removed
```

Inconsistent reports and result/report count mismatches are rejected.

## No-op identity

When neither phase removes an event:

```python
processed.notes is original.notes
```

The report has equal input/output counts and zero removal, group, and affected counts. This preserves valid batches without unnecessary reconstruction.

When a change occurs, a new `NoteEventBatch` is created with the existing `NoteEvent` objects and the unchanged `NOTE_EVENT_SCHEMA_VERSION = "1.0"`. The existing JSON codec serializes only `schema_version` and events; the report is separate.

## Complexity

The implementation uses one duration pass and one dictionary-backed duplicate pass:

```text
time:              O(n)
additional memory: O(n)
```

It does not compare every pair of events and does not copy audio, activations, tensors, or model state.

## Preserved events

The policy keeps overlapping, consecutive, chronologically unordered, zero-confidence, and zero-velocity events when they are not short or exact duplicates. Same-pitch events with different timing and different-pitch events with equal timing are distinct.

## Limitations and future extensions

Policy 1.0 does not implement:

- SAX-023 low-confidence markers or filtering;
- approximate deduplication;
- overlap or monophony resolution;
- timing fusion, quantization, tempo, or notation;
- transposition, final MIDI, or MusicXML;
- endpoint, job-state, persistence, queue, worker, Backend, or Frontend integration.

Any future approximate rule requires explicit evaluation, versioning, and new acceptance criteria rather than silently changing policy `1.0`.
