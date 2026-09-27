# TDD iteration 002 — SAX-041 job status gateway

## Story and scope

SAX-041 exposes the existing FastAPI transcription-job lookup through the Spring Boot product API. The iteration is limited to read-only job status retrieval. It does not add persistence, processing, transitions, progress percentages, polling, or SAX-042.

## Exact base

Backend SAX-040 PR #1 was verified at head `1ab920827e3d12540fb03e530c281758ffeb0ff7`, marked ready, and squash-merged normally with `expected_head_sha`:

```text
c2936f182fd62edd8b0b99f914cab6c40264605d
SAX-040: Add product audio upload gateway
```

`feature/SAX-041-job-status` was created exactly from that squash.

## Contract source

The unchanged AI service defines:

```http
GET /api/v1/transcriptions/{job_id}
```

It uses a UUID path parameter, returns the seven-field `TranscriptionJobResponse`, returns 404 for an unknown job, and currently defines only `UPLOADED` and `FAILED`.

## RED

Tests-only commits preceded production:

```text
9fdd7eb test(SAX-041): define job status application contract
6de3d7c test(SAX-041): define product job status contract
a9b7e8e test(SAX-041): define FastAPI status forwarding and errors
```

Normal read-only CI evidence:

```text
Quality #50
run: 29872980320
job: 88777132917
Java 21 setup: success
Maven verification: expected failure during test compilation
```

The errors were the absent SAX-041 contracts: `GetTranscription`, `TranscriptionStatusController`, `TranscriptionGateway.get(UUID)`, `FastApiTranscriptionClient.get(UUID)`, `INVALID_JOB_ID`, and `TRANSCRIPTION_NOT_FOUND`. Dependency installation was not used as RED.

## GREEN

Production was introduced only after RED:

- `GetTranscription` delegates once and returns the exact gateway instance;
- `TranscriptionGateway` gains the read operation;
- `FastApiTranscriptionClient` sends a bodyless GET to the exact FastAPI path;
- response parsing is reused from SAX-040 and additionally checks requested/returned UUID equality;
- route UUIDs, 404, 422, 5xx, timeout, connection refusal, malformed JSON, unsafe filename, invalid SHA, invalid enums, and blank status receive controlled handling;
- `TranscriptionStatusController` exposes the public GET;
- CORS allows POST, GET, and OPTIONS only for the configured frontend origin.

## REFACTOR

Quality #57 showed that all 62 tests passed and only four files required the pinned Palantir formatter. A temporary read-only diagnostics workflow ran `spotless:apply` and uploaded only formatted source files. The exact formatter output was committed, and the workflow was removed before the final tree.

The final implementation keeps parsing and error translation centralized in the existing client, retains web/application/infrastructure boundaries, and introduces no persistence.

## Tests

Coverage includes:

- exact UUID and one application-port invocation;
- returned-instance preservation and controlled-error propagation;
- public GET 200 and complete seven-field JSON;
- malformed UUID 400 envelope;
- unknown job 404 envelope;
- configured and rejected CORS origins;
- real JDK HTTP server method/path/body inspection;
- absence of multipart on GET;
- FastAPI 404, 422, 500, 503, and unexpected status;
- timeout and connection refusal;
- malformed JSON, incompatible UUID, SHA, enum, filename, and status;
- all previous SAX-040 upload regressions.

## Quality evidence

Functional clean head before documentation:

```text
04f4cd5402d2664dee6744539d27cd063c9df299
Quality #63
run: 29873660514
job: 88779359705
```

Results:

```text
62 tests passed
0 failures
0 errors
0 skipped
247 / 263 lines covered = 93.92%
70 / 86 branches covered = 81.40%
Spotless: 31 Java files clean
Checkstyle: 0 violations
JaCoCo: all checks met
BUILD SUCCESS
```

The workflow used Java 21, `./mvnw verify`, read-only repository permissions, and uploaded external evidence. No generated report or log is committed.

## Cross-repository trace

```text
Frontend GET with job_id
→ Spring controller parses the same UUID
→ GetTranscription passes that UUID unchanged
→ FastApiTranscriptionClient uses the same UUID in the FastAPI path
→ all seven response fields are preserved
```

No shared package was created.

## Limitations

The GET reports only the status already held by FastAPI. There is no processing worker, persistent job store, simulated transition, percentage, ETA, WebSocket, SSE, or long polling. A complete manual three-process E2E was not claimed during this iteration.
