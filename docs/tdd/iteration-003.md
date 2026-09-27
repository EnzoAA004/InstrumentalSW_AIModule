# TDD iteration 003 — SAX-042 review gateway

## Scope

Read and validate an already-produced review snapshot through Spring Boot without persistence or processing.

Base and branch:

```text
d6feb5e552e61842e4ac771b7054588fbc4b86c4
feature/SAX-042-note-review-gateway
```

## RED

Tests preceded production:

```text
1eb3aff test(SAX-042): define transcription review application contract
a3a6caa test(SAX-042): define real FastAPI review forwarding and validation
78df983 test(SAX-042): define public transcription review endpoint
```

They referenced `TranscriptionReview`, `GetTranscriptionReview`, `TranscriptionReviewGateway`, `FastApiTranscriptionReviewClient`, controller/configuration, and stable not-ready behavior before those contracts existed. The branch advanced quickly enough that some intermediate workflow runs were superseded by concurrency; commit order remains the TDD trace.

## GREEN

Production added:

- immutable validated review aggregate, summary, and event contracts;
- independent application port and one-call use case;
- bodyless FastAPI GET client;
- complete manual JSON validation and UUID identity check;
- exact public response DTO;
- controller and stable 400/404/409/502 mappings.

No response is persisted.

## REFACTOR

Validation remains in domain plus infrastructure parsing rather than the controller. Pinned Palantir formatting was applied from a temporary read-only diagnostics artifact, then its workflow was deleted. A Checkstyle regression was resolved by restructuring the JSON test fixture instead of changing the rules.

## Tests

Coverage includes:

- exact UUID and returned-instance preservation;
- HTTP method/path/body inspection through a real JDK HTTP server;
- complete review response;
- malformed route UUID;
- FastAPI 404, 409, 422, 500, 503;
- timeout and connection refusal;
- malformed JSON and UUID mismatch;
- unknown versions;
- inconsistent indices/counts;
- invalid event confidence;
- safe public envelopes and no upstream leakage;
- all prior upload/status regressions.

## Quality

Definitive functional head before documentation:

```text
7c2bf7cc4cf8a49f8b735e7f13aa6f91269f2c24
Quality #88
run 29879571671
Java 21
./mvnw verify
78 tests passed
408 / 449 lines = 90.87%
126 / 175 branches = 72.00%
Spotless clean
Checkstyle clean
JaCoCo gate passed
BUILD SUCCESS
```

The final documentation head is revalidated by the same protected workflow and recorded in the draft PR.

## Boundaries

No inference, upload processing, audio storage, BackgroundTasks, worker, queue, database, new status, review polling, synthetic notes, editing, playback, score/PDF, download, SAX-043, or later story was introduced.
