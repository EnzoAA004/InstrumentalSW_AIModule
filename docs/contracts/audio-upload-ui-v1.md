# Audio upload UI contract v1

## Purpose

SAX-040 provides one browser screen for creating the initial transcription job. The frontend validates the selected file, builds the exact public multipart request, sends it only to the Spring Boot product API, and displays the complete HTTP 202 response.

```text
Next.js
→ Spring Boot product API
→ existing FastAPI AI service
```

The browser does not call FastAPI directly.

## Screen content

The single page contains:

```text
Saxo identity
brief upload explanation
file selector
saxophone selector
input-mode selector
explicit submit button
request status
success result or accessible error summary
```

There is no dashboard, sidebar, complex navigation, or progress route.

## File selector

```html
accept=".mp3,.wav,audio/mpeg,audio/wav"
```

Behavior:

- validates `.mp3` and `.wav` case-insensitively;
- rejects unsupported extensions;
- rejects zero-byte files;
- displays filename and byte size;
- allows replacement before submission;
- does not upload on selection;
- does not read, decode, play, preview, or create a public/object URL.

## Saxophone values

| Visible label | Submitted value |
| ------------- | --------------- |
| Soprano       | `soprano`       |
| Alto          | `alto`          |
| Tenor         | `tenor`         |
| Baritone      | `baritone`      |

## Input-mode values

| Visible label  | Submitted value |
| -------------- | --------------- |
| Solo saxophone | `solo`          |
| Mixture        | `mixture`       |

The interface explains that source separation is not implemented. The `mixture` request remains available because the existing contract records the selected mode.

## Product API configuration

```text
NEXT_PUBLIC_SAXO_API_BASE_URL=http://localhost:8080
```

Request URL:

```text
${NEXT_PUBLIC_SAXO_API_BASE_URL}/api/v1/transcriptions
```

No FastAPI host or port appears in frontend source, configuration, errors, or UI.

## Multipart request

The typed client creates `FormData` in this exact insertion order:

```text
file
saxophone_type
input_mode
```

It sends POST and does not set a manual `Content-Type`; the browser supplies the boundary. It performs no automatic retry and starts no polling.

## Successful response

Only HTTP 202 is accepted. The client validates:

- syntactically valid UUID shape;
- nonblank status and filename;
- safe filename without path separators;
- nonnegative safe integer size;
- lowercase 64-character hexadecimal SHA-256;
- known saxophone and input-mode values.

The result displays:

```text
job_id
status
filename
size_bytes
saxophone_type
input_mode
audio_sha256
```

The user may explicitly reset the screen to begin another upload. The page does not navigate to progress.

## UI states

```text
idle
ready
submitting
success
error
```

Rules:

- submission without a file is rejected locally;
- submitting disables the button and uses an additional synchronous guard;
- double submission produces one API call;
- errors preserve a valid selected file;
- retry is explicit;
- progress is indeterminate text only;
- no percentage is invented.

## Errors

Public Backend envelopes become `TranscriptionApiError` with:

```text
code
message
field
HTTP status
```

Network rejection becomes `BACKEND_UNAVAILABLE`. Malformed or incompatible JSON becomes `INVALID_BACKEND_RESPONSE`. Unknown runtime errors use one readable message without exposing raw bodies, HTML, stack traces, internal URLs, or network details.

## Accessibility

- each control has a visible label;
- file and mode help text use `aria-describedby`;
- file errors set `aria-invalid`;
- the error summary uses `role="alert"`, `tabIndex=-1`, and receives focus;
- submitting text uses `aria-live="polite"`;
- controls are keyboard reachable;
- focus is visibly outlined in amber;
- success/error meaning is textual and not color-only;
- button labels describe their actions.

## Responsive and visual contract

The layout uses a centered single card, two columns where space permits, and one column on narrow screens. Colors are warm background, neutral surfaces, charcoal text, green actions, amber focus, and visible brown borders. There is no blue primary color, emoji, component framework, or decorative animation.

## Limitations

SAX-040 does not include drag-and-drop infrastructure, audio preview, waveform, playback, progress polling, WebSocket, SSE, job progress route, score viewer, confidence markers, editing, downloads, persistence, authentication, analytics, SAX-041, or later stories.
