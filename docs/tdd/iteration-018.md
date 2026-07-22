# TDD iteration 018 — SAX-043 immutable transcription revisions

## Scope

This iteration implements the AI-service boundary for human note editing over an already produced SAX-042 review result. It does not connect upload to inference and does not execute derived-artifact regeneration.

Exact branch base:

```text
6ffe935a6a271096f461424561064f35058c572f
```

That commit is the squash result of SAX-042 AI PR #17.

## RED

Tests were committed before production revision modules:

```text
test(SAX-043): define immutable revision contracts and operations
test(SAX-043): define revision history conflicts and HTTP API
test(SAX-043): require revision zero for a preexisting review
test(SAX-043): require atomic review and revision initialization
```

The first protected run failed because the new domain/application modules and repository implementations did not exist. Dependency installation and the existing SAX-042 suite were not used as the RED condition.

Tests defined:

- frozen revision/event/history/request contracts;
- revision-zero initialization and idempotency;
- source identity preservation;
- all four saxophone offsets;
- empty histories with zero events;
- pitch, onset, and offset update;
- add with default/custom velocity;
- delete and mixed ordered operations;
- stable source and human IDs;
- model confidence preservation and human null confidence;
- no implicit sorting and allowed overlaps;
- invalid MIDI, timing, velocity, duplicate targets, unknown IDs, and atomicity;
- sequential history and detail lookup;
- optimistic conflict;
- idempotent regeneration request;
- absence of artifact bytes and completion claims;
- exact HTTP JSON, 400/404/409/422 envelopes, and absence of historical mutation endpoints.

## GREEN

Production added:

```text
src/saxo_ai/domain/transcription_revisions.py
src/saxo_ai/application/transcription_revisions.py
```

and extended:

```text
application/errors.py
application/ports.py
application/transcription_review.py
infrastructure/repositories.py
api/schemas.py
api/routes.py
main.py
```

Key behavior:

- `RegisterTranscriptionReview` builds revision zero and performs one call to the atomic registration port;
- one shared in-memory snapshot owns review plus revision history while query ports remain separate;
- a preexisting identical review with no history receives exactly one revision zero;
- repeated registration of the same instance is idempotent and a different instance is rejected;
- simulated initialization failure leaves no partial review or revision-zero state;
- revision zero is derived without mutating `WrittenPitchTranscriptionResult` or job status;
- a separate repository owns regeneration requests;
- update/add/delete apply to a temporary complete event list and append only after validation;
- written pitch is authoritative input and concert pitch is derived from the instrument offset;
- optimistic append compares the expected latest revision;
- history and detail return immutable projections;
- regeneration creates only a `REQUESTED` record and never invokes existing exporters.

## REFACTOR

Refactoring kept domain validation separate from transport parsing, centralized operation application and pitch derivation, and represented regeneration status as a read projection backed by a separate request repository. The stored revision itself remains immutable.

Diagnostics found and corrected:

- FastAPI JSON body binding was made explicit with `Body()`;
- the authoritative domain `InvalidRevisionEventError` was re-exported explicitly for stable application imports;
- deterministic UUID expectations were aligned with actual injected factory call order;
- pinned Ruff formatting and import order were applied without changing quality thresholds.

Temporary diagnostic/formatter workflows are not part of the final diff.

## Architecture

```text
RegisterTranscriptionReview
→ build complete revision zero
→ TranscriptionReviewRegistrationRepository.initialize(review, revision zero)
→ one validated shared-snapshot replacement

POST revision
→ CreateTranscriptionRevision
→ validate/apply ordered operations
→ append(expected latest)

GET history/detail
→ immutable repository reads

POST regeneration request
→ RegenerationRequestRepository
→ REQUESTED projection only
```

Existing MIDI, MusicXML, and SVG exporters are not imported or called by the regeneration use case.

## Quality

The protected workflow remains unchanged and runs:

```text
Python 3.11 with real pinned baseline
Python 3.12
Python 3.13
```

The final run and exact metrics are recorded in the PR body after documentation is complete.

No coverage, Ruff, mypy, baseline, or workflow threshold was reduced.

## Remaining boundary

Editing, validation and revision history are implemented.

A regeneration request is recorded explicitly.

Artifact execution remains pending because SAX-043 includes no worker or derived-artifact adapter orchestration.
