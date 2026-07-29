# Note-level AMT evaluation metrics — v1

## Objective

SAX-053 provides model-independent, standard note-level transcription
metrics — precision, recall, F1, and onset-timing error — so SAX-054 can
compare baselines under one common, documented protocol instead of ad hoc
numbers.

## Traceability

```text
SAX-053
→ NoteEventBatch (existing domain contract, model-independent)
→ NoteMatchToleranceSettings / NoteTranscriptionMetrics
→ EvaluateNoteTranscription (application use case)
→ tests/unit/test_note_transcription_metrics.py
→ tests/unit/test_note_transcription_evaluation.py
```

## Matching protocol

Follows the standard MIR note-transcription convention (MIREX / mir_eval
`transcription` module):

- A reference note and an estimated note may only match if
  `pitch_concert_midi` is exactly equal — this is symbolic MIDI pitch, not
  continuous frequency, so there is no cents tolerance.
- Onset must be within `onset_tolerance_seconds` (default `0.05`, the
  standard 50 ms MIREX default).
- Offset is ignored unless `evaluate_offset=True`. When enabled, offset must
  be within `max(offset_ratio * reference_duration, offset_min_tolerance_seconds)`
  (defaults `0.2` and `0.05`, matching mir_eval's defaults).
- Matching is **one-to-one**: within each pitch, reference notes are
  processed in onset order and greedily matched to the closest still-unused
  estimated note inside tolerance. An estimated note can satisfy at most one
  reference note.

## Metrics

- `precision = matched / estimated_count`, `recall = matched / reference_count`,
  `f1_score` their harmonic mean.
- **Convention for empty inputs**: if both reference and estimated are empty,
  precision/recall/F1 are `1.0` (nothing to predict, nothing predicted,
  vacuously perfect). If exactly one side is empty, the ratio against the
  empty side is `0.0`, so precision or recall is forced to `0.0` and
  therefore `f1_score` is `0.0`.
- `mean_onset_error_seconds` / `median_onset_error_seconds` are computed only
  over matched pairs; both are `None` when `matched_count == 0`
  (`NoteTranscriptionMetrics` enforces this — the two states are mutually
  exclusive by construction).

## Complexity note

Matching is `O(n * m)` per pitch group (reference count × estimated count),
not a full Hungarian assignment. For note-level transcription (dozens to a
few hundred notes per pitch per recording) this is fast and simpler than
adding a bipartite-matching dependency; it is not appropriate to reuse for
frame-level or very large candidate sets without revisiting the algorithm.

## Architecture

```text
domain
  NoteMatchToleranceSettings / NoteTranscriptionMetrics — immutable,
  validated, no I/O. Enforces the "onset errors present iff matched_count > 0"
  invariant.

application
  EvaluateNoteTranscription — pure greedy matching + metric computation,
  no I/O, mirrors the PostProcessTranscriptionEvents use-case shape.
```

No infrastructure or API surface is added; SAX-054 is expected to be the
first consumer that runs this against real baseline outputs.
