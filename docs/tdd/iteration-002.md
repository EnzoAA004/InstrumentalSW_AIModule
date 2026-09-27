# TDD iteration 002 — SAX-041 live transcription progress

## Story and exact base

SAX-041 adds a dedicated read-only progress route over the existing job status contract.

Frontend SAX-040 PR #1 was verified at head `f2ff639f4fcee7a7370cea38ea92b14080aaf0b9`, marked ready, and squash-merged normally with `expected_head_sha`:

```text
6af1e8a9a975687f01dacab872ccd763be2cc41e
SAX-040: Add accessible audio upload flow
```

`feature/SAX-041-job-progress` was created exactly from that squash.

## Contract source

The unchanged AI service exposes GET `/api/v1/transcriptions/{job_id}`, returns the same seven job fields as POST, uses 404 for unknown identifiers, and currently defines only `UPLOADED` and `FAILED`.

The Frontend calls the product Backend at port 8080. It does not know the FastAPI host or port.

## RED

Tests-only commits preceded production:

```text
a917866 test(SAX-041): define typed job status client
100a530 test(SAX-041): define progress navigation from upload
a0a7040 test(SAX-041): define accessible progress view and errors
c452301 test(SAX-041): define controlled polling lifecycle
```

Normal CI evidence:

```text
Quality #29
run: 29874075505
job: 88780605389
Node 24.18.0 setup: success
npm 11.6.2 and npm ci: success
quality: expected failure because getTranscription and TranscriptionProgress did not exist
```

Dependency installation was not used as RED.

## GREEN

Production was introduced only after the behavioral tests:

- `getTranscription` validates the UUID, sends an exact Backend GET, accepts only 200, checks response identity, and maps safe failures;
- the SAX-040 result gains `View job progress` while retaining `Upload another audio file`;
- `src/app/transcriptions/[jobId]/page.tsx` supports direct reload from the URL;
- `TranscriptionProgress` renders complete metadata and explicit states;
- `UPLOADED` continues polling, `FAILED` stops, and unknown status stops with a warning;
- recursive `setTimeout` schedules the next request only after successful completion;
- pause, resume, refresh, retry, abort, and stale-response protection are implemented;
- responsive CSS extends the existing warm neutral visual language.

## REFACTOR

Diagnostics exposed and corrected:

1. fake-timer tests originally waited through utilities driven by fake timers; they now resolve controlled promises directly;
2. automatic-update text was split from last-request text for accessible, precise assertions;
3. valid-but-different response UUID and abort propagation received explicit tests instead of lowering branch coverage;
4. recursive polling uses a stable callback reference to satisfy React Hook immutability;
5. the first GET is queued in the mount microtask, avoiding a synchronous state update inside the effect while remaining immediate;
6. the dynamic route keys the client component by `jobId` so each URL receives isolated state;
7. a temporary read-only workflow applied the pinned Prettier output to four files and was deleted before the final tree.

## Tests

Coverage includes:

- valid and invalid UUIDs;
- exact Backend URL, GET method, `encodeURIComponent`, and absence of FastAPI URL;
- HTTP 200, 400, 404, 502, network failure, abort, malformed JSON, incompatible response, and UUID mismatch;
- creation-result navigation to the exact job route and retained reset action;
- loading, UPLOADED, FAILED, unknown status, 404, 502, and network error UI;
- last valid job preserved after a refresh failure;
- manual refresh, pause, resume, retry, back navigation, and accessibility;
- immediate first request and 3000 ms delay after completion;
- no request before the interval and no overlapping requests;
- no scheduling while a request is pending;
- timer cancellation, request abort on unmount, terminal/error stop, and obsolete-response suppression;
- all previous SAX-040 upload and accessibility regressions.

Tests query visible roles, labels, links, status text, and controls rather than relying primarily on snapshots.

## Functional quality evidence

```text
head: cd221cd4c1b39dcfe936e6f6e73c4ab3e59bf19d
Quality: #48
run: 29875367757
job: 88784681110
status: success
Node: 24.18.0
npm: 11.6.2
command: npm run quality
permissions: contents read
```

Results:

```text
7 test files passed
62 tests passed
94.01% statements
91.08% branches
97.72% functions
94.42% lines
ESLint passed
Prettier passed
TypeScript strict passed
Next.js production build passed
```

All global coverage dimensions remain above 90%. No coverage output or quality log is committed.

## Cross-repository contract trace

```text
Frontend getTranscription(job_id)
→ GET Spring /api/v1/transcriptions/{same job_id}
→ Spring GET FastAPI /api/v1/transcriptions/{same job_id}
→ same seven fields returned to the page
```

Evidence is distributed across the Frontend client tests, Backend controller tests, real Backend-to-FastAPI HTTP-server test, and documented comparison with the unchanged AI `routes.py` and `schemas.py`. No shared package was introduced.

## Manual execution

The documented local topology remains FastAPI 8000, Spring 8080, and Next.js 3000. A simultaneous three-process manual E2E was not executed or claimed in this iteration; automated contract evidence is used instead.

## Limitations and excluded stories

The real service currently reports `UPLOADED` or `FAILED`; no processing transition exists. SAX-041 therefore displays server state rather than mathematical progress. There is no percentage, ETA, simulated stage, automatic retry after error, WebSocket, SSE, long polling, persistence, background sync, model execution, SAX-042, or later product story.
