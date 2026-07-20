# TDD iteration 010 — SAX-023

## Scope

Implement only the low-confidence review marker after SAX-022. SAX-023 annotates every surviving `NoteEvent`, preserves the complete raw and postprocessed transcription chain, and exposes a deterministic output-only JSON view.

SAX-030, transposition, FastAPI wiring, job-state changes, Backend, and Frontend remain outside this iteration.

## Acceptance criteria

- immutable configurable threshold;
- default threshold `0.50`;
- strict comparison `confidence < threshold`;
- one `is_low_confidence` boolean per postprocessed event;
- no event filtering, hiding, replacement, or reordering;
- event object identity preserved;
- SAX-022 result and report preserved;
- raw model/checkpoint/inference provenance preserved;
- confidence documented as an uncalibrated model signal;
- versioned deterministic JSON view;
- original NoteEvent schema and serializer unchanged.

## Policy decision

```text
LOW_CONFIDENCE_POLICY_VERSION       1.0
LOW_CONFIDENCE_VIEW_SCHEMA_VERSION  1.0
DEFAULT_LOW_CONFIDENCE_THRESHOLD    0.50
CONFIDENCE_INTERPRETATION           model_signal_not_calibrated_accuracy
```

The initial `0.50` value is an operational review threshold, not an accuracy claim. In particular, `0.8` does not mean 80% accuracy.

The exact rule is:

```text
confidence < threshold  → marked
confidence = threshold  → not marked
confidence > threshold  → not marked
```

No `<=`, epsilon, rounding, calibration, probability conversion, or engine comparison is introduced.

## Architecture

```text
TranscriptionResult
        │
        ▼
PostProcessTranscriptionEvents       SAX-022
        │
        ▼
PostProcessedTranscriptionResult
        │
        ▼
MarkLowConfidenceEvents              SAX-023
        │
        ▼
ConfidenceAnnotatedTranscriptionResult
        ├── original SAX-022 result
        ├── ordered event annotations
        └── LowConfidenceReport
```

Domain owns immutable constants, settings, annotation, report, result, and invariants. Application owns classification and serialization. Infrastructure, API, baseline, workflow, Backend, and Frontend have no functional changes.

## RED

Three tests-only commits preceded all production code:

```text
6745c90  test(SAX-023): define low-confidence annotation contract
1aeb637  test(SAX-023): define transcription confidence preservation
9d6f6dd  test(SAX-023): define versioned confidence view
```

Focused execution before production existed:

```text
3 errors during collection

ModuleNotFoundError: No module named 'saxo_ai.domain.note_confidence'
ModuleNotFoundError: No module named 'saxo_ai.application.note_confidence'

RED_EXIT_CODE=2
```

The failures were caused by the expected missing SAX-023 contracts and application modules.

## GREEN

The minimum implementation introduced:

- `LowConfidenceSettings`;
- `ConfidenceAnnotatedNoteEvent`;
- `LowConfidenceReport`;
- `ConfidenceAnnotatedTranscriptionResult`;
- `MarkLowConfidenceEvents`;
- `serialize_confidence_annotated_result`.

The use case reads only `PostProcessedTranscriptionResult`, computes `event.confidence < threshold`, and creates one annotation for every event. It does not invoke the model or repeat SAX-022 filtering/deduplication.

Focused GREEN result on Python 3.13.5:

```text
54 passed
```

A test initially searched the complete JSON string for the substring `accuracy`. That incorrectly matched the required interpretation value `model_signal_not_calibrated_accuracy`. The test was corrected to reject forbidden JSON field names rather than reject the required explanatory value.

## REFACTOR

- `_is_low_confidence` centralizes the strict comparison;
- contract constants are centralized in `domain.note_confidence`;
- the use case classifies and counts events in one traversal;
- result validation checks references, order, and marked count in one traversal;
- the serializer reuses `NOTE_EVENT_FIELDS`;
- no NoteEvent validation rule is duplicated;
- no event or batch is reconstructed;
- no audio, activation, tensor, model, or checkpoint is copied.

Complexity:

```text
time:                O(n)
additional memory:   O(n)
```

After refactor:

```text
54 passed
python -m compileall -q src tests  PASS
```

## Threshold borders

```text
threshold 0.50, confidence 0.499999  → true
threshold 0.50, confidence 0.500000  → false
threshold 0.50, confidence 0.500001  → false
```

```text
threshold 0.0  → no valid event is marked
threshold 1.0  → confidence below 1.0 is marked; exactly 1.0 is not marked
```

Valid configuration values are normalized to `float`. Booleans, strings, `None`, NaN, infinities, negatives, and values above one are rejected.

## Preservation

For every result:

```text
len(annotated_events)
=
len(original.notes.events)
=
report.input_event_count
```

For every index:

```python
annotated.annotated_events[index].event is annotated.original.notes.events[index]
```

The implementation preserves confidence `0.0`, confidence at the threshold, confidence `1.0`, velocity `0`, overlaps, chronological disorder, and every event retained by SAX-022.

The following remain reachable through nested original contracts:

- raw `TranscriptionResult`;
- raw NoteEventBatch;
- model identity;
- engine version and source revision;
- model revision;
- checkpoint filename and SHA-256;
- inference settings and confidence method;
- postprocessed NoteEventBatch;
- SAX-022 settings and report.

No provenance is copied into duplicate strings.

## Report

`LowConfidenceReport` records:

```text
settings
input_event_count
low_confidence_count
regular_confidence_count
affected_event_count
```

Invariant:

```text
input_event_count
=
low_confidence_count
+
regular_confidence_count
```

`affected_event_count` equals `low_confidence_count` and means marked, never removed. All counters are non-negative integers and booleans are rejected.

## Serialization

The output-only serializer uses only the standard library and emits:

```text
schema_version
policy_version
low_confidence_threshold
confidence_interpretation
confidence_method
summary
events
```

Each event contains the original five `NOTE_EVENT_FIELDS` plus only `is_low_confidence`. JSON booleans are real booleans. Order and all original values are preserved.

Serialization is deterministic:

```python
json.dumps(
    document,
    sort_keys=True,
    allow_nan=False,
    separators=(",", ":"),
)
```

No deserializer is implemented. The original NoteEvent schema remains `1.0`, and `serialize_note_event_batch` remains unchanged and does not include the marker.

The view deliberately omits correctness, accuracy, calibrated probability, SAX-022 removal details, paths, bytes, and Python objects.

## Confidence interpretation

Confidence is an internal signal declared by the transcription engine. It is not a calibrated probability that a note is correct and is not a guaranteed measure of musical accuracy.

The marker means only that the signal is below the configured operational threshold and the event should be prioritized for human review. It does not mean the note is wrong or should be removed, and values are not assumed comparable between different engines.

## Local results

The execution sandbox blocks normal GitHub cloning and general package installation through outbound DNS. The focused workspace was reconstructed from authenticated GitHub contents.

Executed locally on Python 3.13.5:

```text
focused pytest: 54 passed
focused coverage: 218 statements, 12 missed
focused branches: 52, 10 partial
focused coverage: 92%
compileall: PASS
```

Ruff 0.15.22 WASM was obtained through the available package registry and used to reproduce the exact repository formatting configuration. It identified one remaining comprehension layout in `note_confidence_serialization.py`; applying the canonical output resolved the protected format failure.

The complete editable installation and full repository gate are not represented as local executions because the environment could not perform a normal repository clone or install the complete Python dependency set. The protected GitHub Actions matrix is the complete-repository evidence.

## CI diagnostic history

Initial functional runs reached pytest and Ruff lint but stopped at `ruff format --check`. The gate and workflow were not weakened. The exact formatter was reproduced, all six new Python files were compared, and only the serializer required a canonical layout change.

The final functional matrix is:

```text
Quality #119
run ID: 29775277273

Python 3.11: success
Python 3.12: success
Python 3.13: success
```

Python 3.11 completed:

- `python scripts/install_baseline.py`;
- exact PEP 610 checks for both pinned distributions;
- pinned checkpoint resolution and SHA-256 verification;
- real CPU inference;
- FFmpeg-required integrations;
- complete pytest/coverage/Ruff/format/mypy gate.

Python 3.12 and 3.13 installed the core, executed FFmpeg integrations and the complete quality gate, and skipped only the explicitly marked real baseline integration.

## Complete matrix results

```text
Python 3.11:
  387 passed
  real baseline integration executed

Python 3.12 / Python 3.13:
  386 passed
  1 baseline_integration skipped explicitly
```

Coverage totals:

```text
1287 statements
64 missed
326 branches
49 missing branches
92.99% total coverage
```

Quality tools:

```text
Ruff lint: all checks passed
Ruff format: 68 files already formatted
mypy: no issues in 68 source files
```

## Limitations and stories not implemented

Not implemented:

- confidence-based deletion, hiding, or ordering;
- modification of confidence or velocity;
- calibration or accuracy estimation;
- probability of correctness/error;
- comparison across engines;
- user-, instrument-, or environment-specific threshold;
- FastAPI connection or endpoint;
- job-state changes;
- Frontend integration;
- SAX-030 or transposition work;
- MIDI, tempo, quantization, or MusicXML;
- persistence, workers, or queues;
- second baseline, training, or datasets.

SAX-042 may consume the output view in a future story while preserving the semantics and limitations documented in `docs/contracts/note-confidence-v1.md`.
