# Job progress UI contract v1

## Purpose

SAX-041 lets a user open a dedicated route for an existing transcription job and repeatedly read its current server status.

```text
Next.js /transcriptions/{job_id}
→ Spring Boot GET /api/v1/transcriptions/{job_id}
→ existing FastAPI GET /api/v1/transcriptions/{job_id}
```

The browser knows only the product Backend URL. It does not know or call FastAPI.

## Navigation

After successful SAX-040 creation, the result keeps `Upload another audio file` and adds:

```text
View job progress
```

The link is exactly:

```text
/transcriptions/{job_id}
```

The dynamic App Router route reads the identifier from the URL, so a browser reload does not depend on component state, localStorage, sessionStorage, or cookies.

## HTTP client

```typescript
getTranscription(jobId: string, signal?: AbortSignal): Promise<TranscriptionJob>
```

Rules:

- validates UUID syntax before `fetch`;
- encodes the validated path segment;
- uses `NEXT_PUBLIC_SAXO_API_BASE_URL`, defaulting to `http://localhost:8080`;
- sends GET without multipart or body;
- accepts only HTTP 200;
- validates the same seven-field `TranscriptionJob` contract as SAX-040;
- requires the response UUID to equal the requested UUID;
- maps public error envelopes, unavailable Backend, malformed JSON, and incompatible jobs;
- does not retry internally.

## Displayed job data

The page displays:

```text
Job ID
Current status
Filename
Saxophone
Audio mode
File size
Audio SHA-256
automatic update state
```

No notes, confidence markers, timeline, score, player, percentage, ETA, or inferred processing stage is displayed.

## Known statuses

The unchanged AI service currently defines only:

```text
UPLOADED
FAILED
```

Policy:

- `UPLOADED`: active; automatic polling may continue;
- `FAILED`: terminal; automatic polling stops;
- any other nonblank status: display the exact value, show a contract warning, stop automatic polling, and allow manual refresh.

Unknown status is never converted to success.

## Controlled polling

Default interval:

```text
3000 ms
```

Lifecycle:

1. first GET is queued immediately after mount;
2. at most one request may be active;
3. a new timer is created only after the previous request resolves successfully with `UPLOADED`;
4. recursive `setTimeout` is used instead of overlapping `setInterval`;
5. `FAILED`, unknown status, or any error stops automatic polling;
6. network and server errors are not automatically retried;
7. unmount clears the timer and aborts the active request;
8. request sequence numbers prevent an obsolete response from replacing newer state.

## Controls

```text
Refresh now
Pause automatic updates
Resume automatic updates
Try again
Back to upload
```

- pause clears the timer and aborts an active request;
- resume issues an immediate request;
- manual refresh is disabled while a request is active;
- `Try again` is manual and visible after an error.

## View states

```text
loading
active
paused
terminal
error
unknown_status
```

The last valid `TranscriptionJob` is stored independently from the current view state. A later transient failure therefore preserves the last successful metadata while showing an error and pausing automatic updates.

## Accessibility

- one `h1` for the route;
- current status and polling text use `aria-live="polite"`;
- errors and unknown-status warnings use `role="alert"`;
- error summaries receive programmatic focus;
- controls have explicit visible text and keyboard operation;
- focus remains visible;
- states are represented textually, never only by color;
- long identifiers and SHA-256 values wrap visibly;
- no mandatory animation or animated progress bar is used.

## Responsive behavior

The existing warm neutral visual language is preserved. Metadata rows collapse to one column on narrow screens, and progress controls become full-width stacked actions.

## Errors

Public Backend envelopes preserve their safe message and code. Client-only failures use:

```text
INVALID_JOB_ID
BACKEND_UNAVAILABLE
INVALID_BACKEND_RESPONSE
```

Raw JSON, HTML, stack traces, private URLs, FastAPI hosts, and network details are not rendered.

## Scope exclusions

No SAX-042, notes, confidence markers, timeline, SVG/PDF viewer, editing, audio/MIDI player, downloads, persistence, background sync, service worker, WebSocket, SSE, long polling, automatic retry, authentication, users, projects, sessions, analytics, or external telemetry is included.
