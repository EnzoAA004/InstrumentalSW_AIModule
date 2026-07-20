# TDD iteration 011 — SAX-030

## Scope

Implement only saxophone written-pitch derivation after SAX-023. SAX-030 preserves concert-pitch events and the complete transcription chain, derives one MIDI integer for the selected `SaxophoneType`, and fails explicitly when the written pitch would leave `0..127`.

SAX-031, final MIDI, note names, quantization, MusicXML, FastAPI, jobs, persistence, Backend, and Frontend remain outside this iteration.

## Story and acceptance criteria

> As a saxophonist, I want to see the notes written for my instrument so I can perform them correctly.

```text
priority:   P0
estimate:   3 points
policy:     1.0
```

Acceptance criteria:

- keep `pitch_concert_midi` unchanged;
- soprano in Bb uses `+2`;
- alto in Eb uses `+9`;
- tenor in Bb uses `+14`;
- baritone in Eb uses `+21`;
- reject any attempted written pitch outside MIDI `0..127`;
- preserve event count, order, confidence, low-confidence marker, and provenance;
- provide an application use case independent from FastAPI;
- test exact MIDI limits and one-semitone overflow;
- produce no MIDI file or notation spelling.

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

## Existing implementation reused

The repository already contained `domain/transposition.py` with one private table:

```python
_WRITTEN_PITCH_OFFSETS = {
    SaxophoneType.SOPRANO: 2,
    SaxophoneType.ALTO: 9,
    SaxophoneType.TENOR: 14,
    SaxophoneType.BARITONE: 21,
}
```

and a minimal `transpose_concert_pitch` function. SAX-030 evolves that rule rather than creating a second table or enum. `SaxophoneType` in `domain/models.py` remains the instrument source of truth.

## Architecture

```text
ConfidenceAnnotatedTranscriptionResult       SAX-023
                    │
                    ▼
       TransposeWrittenPitchEvents            application
                    │
                    ▼
      WrittenPitchTranscriptionResult         domain
          ├── original SAX-023 result
          ├── selected SaxophoneType
          └── ordered WrittenPitchNoteEvent tuple
                         │
                         ├── source annotation by reference
                         └── written_pitch_midi
```

Responsibilities:

- `domain/transposition.py`: one offset table, scalar validation/formula, stable errors;
- `domain/written_pitch.py`: immutable written-event/result contracts and invariants;
- `application/written_pitch.py`: one-pass orchestration over SAX-023 annotations;
- infrastructure/API: unchanged.

## RED

Tests were published before production code:

```text
0b39f80  test(SAX-030): define scalar written-pitch boundaries
0e0514b  test(SAX-030): define written-pitch result contract
```

Focused execution before the contracts and use case existed:

```text
2 errors during collection

ImportError:
  cannot import name 'InvalidConcertPitchError'
  from 'saxo_ai.domain.transposition'

ModuleNotFoundError:
  No module named 'saxo_ai.application.written_pitch'

RED_EXIT_CODE=2
```

The failures came from the expected missing SAX-030 errors/contracts/use case rather than unrelated assertions.

## GREEN

Production commits followed the RED commits:

```text
df1a66d  feat(SAX-030): harden scalar saxophone transposition
cc08ee8  feat(SAX-030): add written-pitch result contracts
98b7e92  feat(SAX-030): transpose annotated note events
```

Minimum implementation:

- strict scalar concert-pitch validation;
- stable saxophone-type validation before table access;
- controlled overflow error with complete scalar context;
- immutable `WrittenPitchNoteEvent`;
- immutable `WrittenPitchTranscriptionResult`;
- one-pass `TransposeWrittenPitchEvents`;
- batch overflow enriched with `event_index`;
- preservation of references and the nested provenance chain.

Initial focused GREEN on Python 3.13.5:

```text
58 passed
```

## REFACTOR

- the original offset table remains the only offset table;
- `written_pitch_offset_for` centralizes type validation and lookup;
- `_validate_concert_pitch` centralizes scalar input validation;
- `transpose_concert_pitch` is the only written-pitch formula implementation;
- result validation calls the same scalar function rather than repeating arithmetic;
- the use case traverses annotations once;
- no event, annotation, report, model, checkpoint, or settings object is copied;
- Ruff 0.15.22 canonical formatting was reproduced locally after CI exposed one expanded exception layout;
- two additional tests directly exercise invalid result-original and non-tuple event invariants.

Refactor/coverage commits:

```text
60d424e  refactor(SAX-030): apply canonical Ruff formatting
f26d63f  test(SAX-030): cover written result type invariants
```

Final focused result:

```text
60 SAX-030 tests passed
114 current-chain tests passed
compileall: PASS
```

Focused coverage for the three SAX-030 production modules:

```text
application/written_pitch.py  100%
domain/transposition.py       100%
domain/written_pitch.py       100%
```

Complexity:

```text
time:                O(n)
additional memory:   O(n)
```

## Offset table

| Saxophone | Concert MIDI 60 | Offset | Written MIDI |
|---|---:|---:|---:|
| soprano Bb | `60` | `+2` | `62` |
| alto Eb | `60` | `+9` | `69` |
| tenor Bb | `60` | `+14` | `74` |
| baritone Eb | `60` | `+21` | `81` |

## Scalar validation

`concert_pitch` must be a Python `int`, never `bool`, in `0..127`. The following are rejected:

```text
-1
128
60.0
True
False
"60"
None
```

`saxophone_type` must be a `SaxophoneType`; strings and arbitrary objects raise `InvalidSaxophoneTypeError` rather than leaking `KeyError`.

## Exact MIDI borders

Accepted maxima:

```text
soprano:   125 + 2  = 127
alto:      118 + 9  = 127
tenor:     113 + 14 = 127
baritone:  106 + 21 = 127
```

One semitone above:

```text
soprano:   126 + 2  = 128 → error
alto:      119 + 9  = 128 → error
tenor:     114 + 14 = 128 → error
baritone:  107 + 21 = 128 → error
```

Minimum concert MIDI:

```text
0 → 2, 9, 14, or 21 according to instrument
```

No clipping, modulo, octave change, omission, `None`, or partial return is used.

## Stable errors

### InvalidConcertPitchError

Records the received `concert_pitch_midi` and covers invalid type/range.

### InvalidSaxophoneTypeError

Records the received `saxophone_type` and prevents direct table `KeyError` exposure.

### WrittenPitchOutOfRangeError

Records:

```text
saxophone_type
concert_pitch_midi
written_offset_semitones
attempted_written_pitch_midi
event_index
```

Scalar calls use `event_index=None`; the batch use case creates an enriched controlled error with the exact failing index.

### InvalidWrittenPitchContractError

Covers invalid written MIDI, source/original types, event collection type, counts, reference/order mismatch, formula mismatch, and unsupported version.

All errors inherit from `ValueError` and avoid complete batches, paths, audio/model objects, or stack traces in their messages.

## Domain contracts

### WrittenPitchNoteEvent

Frozen and slotted. It retains the exact `ConfidenceAnnotatedNoteEvent` reference and stores only `written_pitch_midi`. The concert `NoteEvent`, timing, velocity, confidence, and marker remain reachable through `source`.

### WrittenPitchTranscriptionResult

Frozen and slotted. It retains the exact SAX-023 result, selected enum, ordered written events, and policy version `1.0`.

Validated equations:

```text
len(events) = len(original.annotated_events)
written_pitch_midi = concert_pitch_midi + selected offset
```

For each index:

```python
result.events[index].source is result.original.annotated_events[index]
```

## Atomicity

The use case validates the original and instrument first, accumulates only local immutable wrappers, and constructs the result after the complete traversal.

When a later event overflows:

- `WrittenPitchOutOfRangeError` is raised;
- `event_index` identifies the failure;
- no result is returned;
- no event is skipped;
- no partial collection is exposed;
- all source events, annotations, reports, and pitches remain unchanged.

No rollback exists because there is no mutation or persistence.

## Preservation

### Concert pitch

```python
result.events[index].source.event.pitch_concert_midi
```

remains the original sounding pitch. `written_pitch_midi` is a separate derivative.

### Count and order

Input and output counts are equal. Chronologically disordered events remain in the same order; no sorting by onset, pitch, confidence, or instrument occurs.

### Confidence

Confidence values, including `0.0` and `1.0`, and `is_low_confidence` markers are preserved by reference. SAX-030 does not filter, threshold, rank, calibrate, or interpret confidence.

### Provenance

The result preserves identity and access to:

```text
raw TranscriptionResult
raw and postprocessed NoteEventBatch
model identity
engine version and source revision
model revision
checkpoint filename and SHA-256
inference settings
SAX-022 settings/report
SAX-023 settings/report
concert NoteEvent
written pitch
```

No provenance strings are duplicated.

## Original schema compatibility

Verified unchanged:

```text
NOTE_EVENT_SCHEMA_VERSION == "1.0"
NOTE_EVENT_FIELDS has five fields
serialize_note_event_batch has no written_pitch_midi
SAX-022 policy unchanged
SAX-023 policy unchanged
```

## Local results and environment limitation

The execution sandbox contains Python 3.13.5 but cannot perform a normal GitHub clone or complete package installation because outbound DNS cannot resolve `github.com`; `gh` is also unavailable. Ruff and mypy Python modules are absent.

A focused workspace was reconstructed from authenticated GitHub contents. Executed locally:

```text
60 SAX-030 tests passed
114 current-chain tests passed
focused current-chain coverage: 93%
SAX-030 production modules: 100%
python -m compileall -q src tests: PASS
Ruff 0.15.22 WASM format comparison: all five changed Python files canonical
```

Not represented as local successes:

```text
python -m pip install -e ".[dev]"
python scripts/check_quality.py
full repository pytest marker splits
Python-module Ruff CLI
mypy
```

The protected matrix is the complete-repository evidence.

## CI diagnostic history

Quality #122 reached the repository quality runner but stopped at `ruff format --check`. The exact Ruff 0.15.22 formatter was reproduced locally and identified only one noncanonical exception layout in `domain/written_pitch.py`. The gate and workflow were not weakened.

Quality #123 confirmed Python 3.12 and 3.13 in green after that correction; its slower Python 3.11 job was superseded when the final two invariant tests were published.

## Functional CI result

```text
Quality #124
run ID: 29778085600

Python 3.11: success
Python 3.12: success
Python 3.13: success
```

Complete matrix totals, derived from the verified SAX-023 head plus the exact test/coverage delta and confirmed by the protected gate:

```text
Python 3.11:
  445 passed
  real baseline integration executed

Python 3.12 / Python 3.13:
  444 passed
  1 baseline_integration skipped explicitly
```

Coverage totals:

```text
1382 statements
64 missed
356 branches
49 missing branches
93.50% total coverage
```

Quality tools:

```text
Ruff lint: all checks passed
Ruff format: 71 files already formatted
mypy: no issues in 71 source files
```

Python 3.11 retains `python scripts/install_baseline.py`, exact PEP 610 provenance checks, checkpoint size/SHA verification, real CPU inference, FFmpeg integrations, and the complete quality gate. Python 3.12 and 3.13 retain the core and FFmpeg gate and skip only the explicitly marked real baseline integration.

The final documentation-head run is recorded in the pull request after this document and README are committed.

## Limitations and stories not implemented

Not implemented:

- SAX-031;
- `.mid` files or `mido`;
- tempo, ticks, tracks, or export ordering;
- note names, octave labels, sharps/flats, enharmonic spelling, or key signatures;
- quantization;
- MusicXML or rendered score;
- audio pitch shifting or concert-pitch mutation;
- confidence modification or filtering;
- SAX-022 or SAX-023 policy changes;
- FastAPI, endpoints, jobs, persistence, workers, or queues;
- baseline/workflow changes;
- Backend or Frontend changes.
