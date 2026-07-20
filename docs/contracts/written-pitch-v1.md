# Written saxophone pitch contract — policy 1.0

## Objective

SAX-030 derives the MIDI pitch that must be written for a selected saxophone while preserving the sounding concert pitch produced by transcription. The result is an internal, model-independent domain/application contract. It is not connected to FastAPI, persistence, MIDI export, notation spelling, MusicXML, Backend, or Frontend.

## Traceability

```text
SAX-030
→ RF-040
→ RF-041
→ transpose_concert_pitch
→ TransposeWrittenPitchEvents
→ tests/unit/test_transposition.py
→ tests/unit/test_written_pitch_transcription.py
```

## Policy version

```text
WRITTEN_PITCH_POLICY_VERSION = "1.0"
```

A different policy version is rejected. No implicit migration or coercion occurs.

## Concert pitch and written pitch

`NoteEvent.pitch_concert_midi` is the sounding concert pitch and remains the source of truth. SAX-030 never replaces or mutates it.

The written pitch is derived separately:

```text
written_pitch_midi
=
pitch_concert_midi
+
written_offset_semitones
```

Example for alto saxophone:

```text
concert pitch: 60
written offset: +9
written pitch: 69
```

After processing:

```python
result.events[0].source.event.pitch_concert_midi == 60
result.events[0].written_pitch_midi == 69
```

## Supported instruments and offsets

`SaxophoneType` in `src/saxo_ai/domain/models.py` is the only source of instrument identities. The existing table in `domain/transposition.py` is the only source of written offsets.

| SaxophoneType | Instrument | Written offset |
|---|---|---:|
| `SOPRANO` | soprano in Bb | `+2` |
| `ALTO` | alto in Eb | `+9` |
| `TENOR` | tenor in Bb | `+14` |
| `BARITONE` | baritone in Eb | `+21` |

For concert MIDI `60`:

```text
soprano  → 62
alto     → 69
tenor    → 74
baritone → 81
```

No second table, string-to-enum conversion, instrument alias, or dynamic offset is introduced.

## Scalar function

```python
transpose_concert_pitch(
    concert_pitch: int,
    saxophone_type: SaxophoneType,
) -> int
```

The function validates both inputs, looks up the single documented offset, applies the formula once, validates the attempted written pitch, and returns a Python `int`.

### Concert-pitch input

Valid input is a real Python `int` in `0..127`. Booleans are rejected even though `bool` subclasses `int`.

Rejected examples:

```text
-1
128
60.0
True
False
"60"
None
```

No numeric, string, or enum coercion occurs.

### Saxophone input

`saxophone_type` must be an existing `SaxophoneType` instance. Strings and arbitrary objects raise a controlled error; a `KeyError` from the offset table is never exposed.

## Exact MIDI boundaries

The resulting written pitch must satisfy:

```text
0 <= written_pitch_midi <= 127
```

### Exact accepted maximum

| Instrument | Maximum concert pitch | Written result |
|---|---:|---:|
| soprano | `125` | `127` |
| alto | `118` | `127` |
| tenor | `113` | `127` |
| baritone | `106` | `127` |

### One semitone above

| Instrument | Concert pitch | Attempted written pitch | Result |
|---|---:|---:|---|
| soprano | `126` | `128` | controlled error |
| alto | `119` | `128` | controlled error |
| tenor | `114` | `128` | controlled error |
| baritone | `107` | `128` | controlled error |

### Minimum concert pitch

Concert MIDI `0` is valid for every supported saxophone:

```text
soprano  → 2
alto     → 9
tenor    → 14
baritone → 21
```

The policy never clips to `127`, uses modulo `128`, changes octave, omits an event, returns `None`, or continues with a partial result.

## Stable errors

All public transposition errors inherit from `ValueError` for general compatibility.

### InvalidConcertPitchError

Raised when concert pitch has an invalid type or lies outside `0..127`.

It records:

```text
concert_pitch_midi
```

### InvalidSaxophoneTypeError

Raised when the instrument is not a `SaxophoneType` instance.

It records:

```text
saxophone_type
```

### WrittenPitchOutOfRangeError

Raised when valid scalar inputs produce an attempted written pitch outside MIDI range.

It records:

```text
saxophone_type
concert_pitch_midi
written_offset_semitones
attempted_written_pitch_midi
event_index  # None for scalar use, integer for batch use
```

Messages identify the attempted value and MIDI range without embedding complete batches, audio information, model objects, paths, or stack traces.

### InvalidWrittenPitchContractError

Raised when a written-event/result container violates reference, count, version, value, or structural invariants.

## Domain contracts

### WrittenPitchNoteEvent

```python
@dataclass(frozen=True, slots=True)
class WrittenPitchNoteEvent:
    source: ConfidenceAnnotatedNoteEvent
    written_pitch_midi: int
```

Invariants:

- `source` is an existing SAX-023 annotation;
- the annotation is retained by reference;
- the concert `NoteEvent` remains reachable by `source.event` and is retained by reference;
- `written_pitch_midi` is a Python `int`, never `bool`, in `0..127`;
- the object is immutable;
- no onset, offset, velocity, confidence, or low-confidence marker is copied.

The source of truth for all non-derived values is:

```python
written_event.source.event
```

### WrittenPitchTranscriptionResult

```python
@dataclass(frozen=True, slots=True)
class WrittenPitchTranscriptionResult:
    original: ConfidenceAnnotatedTranscriptionResult
    saxophone_type: SaxophoneType
    events: tuple[WrittenPitchNoteEvent, ...]
    policy_version: str = WRITTEN_PITCH_POLICY_VERSION
```

Required invariants:

```text
len(events) = len(original.annotated_events)
```

For every index:

```python
result.events[index].source is result.original.annotated_events[index]
```

and:

```text
written_pitch_midi
=
source.event.pitch_concert_midi
+
offset for result.saxophone_type
```

A count mismatch, different reference, changed order, incorrect derived pitch, invalid instrument, non-tuple event collection, invalid original, or unsupported version is rejected.

## Application use case

```python
TransposeWrittenPitchEvents().execute(
    original: ConfidenceAnnotatedTranscriptionResult,
    saxophone_type: SaxophoneType,
) -> WrittenPitchTranscriptionResult
```

The use case:

1. validates the complete input and saxophone type before traversal;
2. traverses annotations once;
3. reads `source.event.pitch_concert_midi`;
4. delegates scalar derivation to `transpose_concert_pitch`;
5. creates one lightweight `WrittenPitchNoteEvent` per source;
6. preserves source references and order;
7. returns an immutable complete result.

It does not execute the model, repeat SAX-022, repeat SAX-023, interpret confidence, mutate previous objects, or create product artifacts.

Complexity:

```text
time:                O(n)
additional memory:   O(n)
```

## Atomicity

The use case builds its result only after every annotation has been transposed successfully. If a later event exceeds MIDI range:

- the whole operation raises `WrittenPitchOutOfRangeError`;
- the error contains the failing `event_index`;
- no result object is returned;
- no event is omitted;
- no partial collection is exposed;
- every input object remains unchanged.

No rollback mechanism is needed because the operation has no mutation or persistence.

## Order and empty input

An empty annotated result produces:

```text
events = ()
```

and retains the exact original object.

For non-empty input, SAX-023 order is preserved exactly. SAX-030 does not sort by concert pitch, written pitch, onset, confidence, marker, or instrument.

## Confidence preservation

SAX-030 does not interpret or modify confidence. A low-confidence event and a regular event are transposed by the same scalar rule.

For every index:

```python
result.events[index].source.is_low_confidence
is
result.original.annotated_events[index].is_low_confidence
```

Confidence values `0.0` and `1.0`, velocity `0`, overlaps, and chronological disorder remain accessible through the same source objects.

## Provenance preservation

`WrittenPitchTranscriptionResult.original` is the exact SAX-023 result. The nested chain keeps:

```text
raw TranscriptionResult
raw NoteEventBatch
model identity
engine version
engine source revision
model revision
checkpoint filename and SHA-256
inference settings and confidence method
PostProcessedTranscriptionResult
SAX-022 settings and report
ConfidenceAnnotatedTranscriptionResult
SAX-023 settings and report
concert-pitch NoteEvent
written-pitch derivative
```

No provenance string is duplicated into the written event.

## Original schemas remain unchanged

SAX-030 does not modify:

```text
NoteEvent
NoteEventBatch
NOTE_EVENT_SCHEMA_VERSION = "1.0"
NOTE_EVENT_FIELDS
serialize_note_event_batch
SAX-022 policy
SAX-023 policy
```

`written_pitch_midi` is not added to the original NoteEvent JSON serializer.

## Architectural boundaries

The new domain/application modules do not import:

```text
fastapi
torch
huggingface_hub
hf_midi_transcription
piano_transcription_inference
subprocess
tempfile
mido
```

Infrastructure, API, workflow, and baseline runtime are unchanged.

## Relationship with later stories

### SAX-031

A future MIDI exporter may consume concert or written-pitch results according to an explicit artifact contract. SAX-030 does not write `.mid`, add `mido`, create tracks, convert seconds to ticks, set tempo, or sort for export.

### SAX-034

A future MusicXML implementation may use written pitch plus instrument transposition metadata. SAX-030 does not create MusicXML, measures, accidentals, key signatures, or notation spelling.

## Absence of musical spelling

Policy 1.0 works only with MIDI integers. It does not produce:

```text
C4
C#4
Db4
note names
octave labels
enharmonic spelling
accidentals
key signatures
```

Those choices require later notation context and are not derivable from one MIDI integer alone.

## Limitations

Not included:

- saxophone variants beyond the four existing enum members;
- configurable or user-defined offsets;
- automatic octave correction;
- audio pitch shifting;
- confidence filtering or calibration;
- MIDI generation;
- tempo, ticks, tracks, or quantization;
- note names or enharmonic spelling;
- MusicXML or rendered score;
- FastAPI, jobs, persistence, workers, queues, Backend, or Frontend integration.
