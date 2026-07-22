# TDD iteration 017 — SAX-042 review snapshot API

## Scope

This iteration adds only the read baseline from an already-produced `WrittenPitchTranscriptionResult` to an immutable HTTP review snapshot.

Base:

```text
b8e0b59eda4600f4b931e039b4d96383fd8f6073
```

Branch:

```text
feature/SAX-042-review-snapshot-api
```

## RED

Tests were committed before production:

```text
1179756 test(SAX-042): add real written-pitch review fixture
20ecc5c test(SAX-042): define job-linked review repository and view
ffb678d test(SAX-042): define review API and not-ready errors
```

They referenced repository, registration, query, view, schemas, endpoint, and errors that did not yet exist. The protected tests-only run was cancelled by the workflow concurrency policy when the branch advanced; no dependency failure is presented as RED.

A later regression test also preceded its fix:

```text
ed910ff test(SAX-042): require stable invalid review job ID envelope
d39eec4 feat(SAX-042): map malformed review UUID to stable 400
```

## GREEN

Production introduced:

- independent `TranscriptionReviewRepository` protocol;
- identity-preserving in-memory implementation;
- internal `RegisterTranscriptionReview`;
- `GetTranscriptionReview` with unknown/not-ready/available outcomes;
- immutable versioned snapshot/summary/event views;
- injectable repository composition;
- read-only FastAPI endpoint and exact 400/404/409 envelopes.

No HTTP write path or producer was added.

## REFACTOR

Review validation and serialization are centralized in `application/transcription_review.py`. Existing note, confidence, and written-pitch contracts remain authoritative. Temporary read-only diagnostics were used only to obtain quality/format evidence and were removed from the final tree. The protected `quality.yml` remains unchanged.

## Tests

Coverage includes:

- repository miss and identity-preserving save/get;
- unknown job and not-ready result;
- instrument mismatch at registration;
- exact source order and indices;
- concert/written MIDI preservation;
- onset, offset, velocity, confidence, and marker preservation;
- event and low-confidence counts;
- threshold 0 and 1;
- all four saxophone types;
- empty, one-event, and multi-event shapes;
- deterministic repeated views;
- exact JSON without duration or note names;
- stable malformed UUID, 404, and 409 envelopes;
- absence of a public write endpoint;
- full regression suite.

## Quality evidence

The first complete diagnostics execution on Python 3.13 collected:

```text
938 passed, 1 skipped
91.68% total coverage
Ruff identified one import-order issue
```

The import was corrected without reducing the 90% threshold. The definitive protected Python 3.11/3.12/3.13 matrix is recorded in the draft PR body after the final documentation head completes.

## Architectural boundaries

The endpoint reads only registered domain output. It does not execute inference, process an upload, store audio, add job states, run background work, create synthetic notes, or begin SAX-043.
