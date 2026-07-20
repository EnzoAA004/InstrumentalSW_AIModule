# TDD iteration 009 — SAX-022

## Scope

Implement only deterministic filtering of short and exact duplicate `NoteEvent` values after SAX-021. SAX-023, FastAPI integration, job transitions, storage, Backend, and Frontend remain outside this iteration.

## Acceptance criteria

- configurable immutable minimum duration, default `0.030` seconds;
- strict boundary: shorter removed, equal/longer retained;
- exact duplicate identity by pitch, onset, and offset;
- representative chosen by confidence, velocity, then first appearance;
- duration filtering before deduplication;
- first group position retained in output;
- affected-event report with enforced invariants;
- original `TranscriptionResult` and producer provenance retained;
- no-op returns the original `NoteEventBatch` object;
- schema `1.0` and its JSON codec remain unchanged.

## Interpretation of invalid

`NoteEvent` continues to own structural validation. SAX-022 does not repair or convert `InvalidNoteEventError`. Here, removable means only a valid event shorter than policy or an exact duplicate of another survivor.

## Policy and architecture

```text
TranscriptionResult
        │
        ▼
PostProcessTranscriptionEvents
        ├── event.duration_seconds < minimum
        ├── exact key dictionary
        ├── confidence/velocity tie-breaker
        ▼
PostProcessedTranscriptionResult
        ├── original TranscriptionResult
        ├── processed NoteEventBatch 1.0
        └── NoteEventPostProcessingReport
```

Domain owns immutable settings, version, report, invariants, and result containers. Application owns the two-phase O(n) algorithm. Infrastructure and API have no functional changes.

## RED

Two tests-only commits preceded production:

```text
2ee4f5d  test(SAX-022): define deterministic NoteEvent postprocessing
c794a58  test(SAX-022): define transcription result postprocessing
```

Focused execution before production existed:

```text
collected 0 items / 2 errors

ModuleNotFoundError: No module named 'saxo_ai.domain.note_event_postprocessing'
ModuleNotFoundError: No module named 'saxo_ai.application.note_event_postprocessing'

RED_EXIT_CODE=2
```

The failures occurred for the expected missing contract and use case, not from an unrelated assertion.

## GREEN

The minimum implementation added:

- `NoteEventPostProcessingSettings` with strict numeric validation;
- policy and duplicate-policy constants;
- report and result invariants;
- duration filtering using `event.duration_seconds`;
- exact dictionary key `(pitch, onset, offset)`;
- deterministic representative selection;
- preservation of original result and no-op batch identity.

Focused result on Python 3.13.5:

```text
52 passed in 0.29s
```

## REFACTOR

- `_duplicate_key` centralizes identity;
- `_candidate_is_preferred` centralizes confidence/velocity ranking;
- the dictionary stores the first logical output index for each group;
- a later winner replaces the object in that first slot;
- no new batch is created when both removal counts are zero;
- each input event is traversed by at most the duration pass and duplicate pass;
- report equations are enforced by domain construction.

After refactor:

```text
52 passed
python -m compileall -q src tests  PASS
```

## Duration edges

```text
minimum 0.000: valid events are not removed by duration
0.029999 < 0.030: removed
0.030000 = 0.030: retained
0.030001 > 0.030: retained
```

No rounding or approximate comparison is performed.

## Duplicate rules and tie-breakers

Exact identity uses only pitch, onset, and offset. Confidence and velocity do not affect grouping. Selection is greater confidence, then greater velocity, then first original object. Approximate times, different pitches, different onsets/offsets, overlaps, and out-of-order events remain distinct.

Short events are removed before grouping, so duplicate short events contribute only to `short_duration_removed_count`.

## Order and no-op

The group occupies the first surviving appearance's output position, even when a later object wins. Independent relative order is preserved. No chronological sort is introduced.

A no-op preserves:

```python
processed.original is raw_result
processed.notes is raw_result.notes
```

Model identity, engine version/source revision, model revision, checkpoint, and transcription settings remain reachable only through `processed.original`.

## Report

The report contains settings, input/output counts, short removals, duplicate removals, duplicate groups, and calculated affected count. Negative/non-integer counters, inconsistent count equations, impossible group counts, invalid settings, and result/report count mismatches are rejected.

## Serialization

The processed batch uses the existing `serialize_note_event_batch` and `deserialize_note_event_batch` codec. Round trip remains schema `1.0`; policy and report fields are not added to batch JSON.

## Local environment results

The execution environment could not clone GitHub or install missing packages because outbound DNS is disabled. A faithful focused workspace was reconstructed from authenticated GitHub file contents.

Executed locally:

```text
Python 3.13.5
focused pytest: 52 passed
compileall: PASS
```

The local environment did not contain Ruff or mypy, and a complete repository checkout was unavailable, so full local gate commands are not represented as successful. The authoritative complete-repository verification is the protected GitHub Actions matrix recorded below.

## CI results

Functional draft-PR run:

```text
Quality #104
run ID: 29767153405
Python 3.11: success
Python 3.12: success
Python 3.13: success
```

Python 3.11 completed `python scripts/install_baseline.py`, exact PEP 610 verification for both pinned Git distributions, checkpoint size/SHA validation, real CPU inference, all 333 tests, coverage, Ruff lint, Ruff format, and strict mypy. Python 3.12 and 3.13 installed the core, explicitly skipped only the real baseline integration, and passed the complete core and FFmpeg gate.

The final documentation-head matrix is recorded in the pull request after this document commit.

## Coverage and quality

The complete Python 3.11 gate reported:

```text
333 passed
1176 statements, 60 missed
286 branches, 45 missing
coverage: 92.82%
Ruff: all checks passed
Ruff format: 62 files already formatted
mypy: no issues in 62 source files
```

The focused behavior covers settings, all duration boundaries, exact/approximate duplicate distinctions, tie-breakers, phase order, output order, report invariants, no-op identity, provenance, serialization, and forbidden imports.

## Limitations and stories not implemented

Not implemented: SAX-023 confidence threshold or marker, approximate deduplication, overlap/monophony policy, quantization, tempo, transposition changes, final MIDI, MusicXML, model changes, training, datasets, HTTP wiring, endpoints, jobs, persistence, workers, queues, Backend, or Frontend.
