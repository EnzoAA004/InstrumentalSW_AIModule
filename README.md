# InstrumentalSW Frontend

Accessible Next.js interface for InstrumentalSW (Saxo). SAX-040 creates transcription jobs, SAX-041 displays current server status, SAX-042 exposes a read-only note review, SAX-043 adds explicit editing through immutable revisions, SAX-044 reattaches the original audio locally for synchronized visual playback, and SAX-045 downloads already-materialized revision artifacts through the product API.

```text
Browser / Next.js :3000
  → Spring Boot product API :8080
    → internal FastAPI AI service :8000
```

The browser never calls or configures FastAPI directly.

## Requirements

- Node.js 24.18.0 LTS
- npm 11.6.2

Pinned stack:

```text
Next.js:              16.2.11
React / React DOM:    19.2.8
TypeScript:           5.8.3
Vitest:               4.1.10
Testing Library:      16.3.2
user-event:           14.6.1
ESLint:               9.39.2
Prettier:             3.9.6
jsdom:                29.1.1
```

## Install and run

```bash
npm ci
npm run dev
```

The page runs at `http://localhost:3000`. Start Spring separately at `http://localhost:8080`; Spring contacts FastAPI on port 8000.

## Configuration

```text
NEXT_PUBLIC_SAXO_API_BASE_URL=http://localhost:8080
```

The local Backend URL is the fallback. Do not configure a FastAPI URL in the browser.

## Quality

```bash
npm run test
npm run lint
npm run format:check
npm run typecheck
npm run build
npm run quality
```

`npm run quality` executes the full sequence. Vitest enforces at least 90% global coverage for statements, branches, functions, and lines. TypeScript runs in strict mode, and a production Next.js build is mandatory.

## Create a job

1. Select one `.mp3` or `.wav` file.
2. Choose `soprano`, `alto`, `tenor`, or `baritone`.
3. Choose `solo` or `mixture`.
4. Submit manually.
5. Next.js sends exact multipart fields to Spring Boot.
6. HTTP 202 displays all returned job fields.

The browser lets `fetch` create the multipart boundary. It does not upload automatically.

## View current job status

```text
/transcriptions/{job_id}
```

The UUID is in the URL, so reload requires no localStorage, sessionStorage, or cookies. The typed client calls only the Backend and validates the complete response identity.

Polling uses one request at a time, recursive `setTimeout`, `AbortController`, cleanup, and explicit pause/resume controls. No percentage, ETA, or invented stage is shown.

## View transcription notes

```text
/transcriptions/{job_id}/review
```

The read-only route sends one bodyless GET to Spring, validates the complete versioned payload, and displays all notes in an accessible timeline and semantic table. Confidence remains a model signal and is never presented as calibrated accuracy.

A successful empty review is distinct from a not-ready result. The view links explicitly to both the editor and synchronized playback. SAX-045 resolves revision history and displays downloads for the latest concrete revision.

## Edit transcription notes

```text
/transcriptions/{job_id}/review/edit
```

The editor loads revision history first and then loads the latest revision detail. It keeps immutable server revision, local editable draft, and validation/save state separate. Fetched responses are never mutated and stable `event_id` values remain identities and React keys.

The latest revision supports explicit update, addition, deletion, discard, and one-batch save. There is no autosave or request per keystroke. Historical revisions are read-only, conflicts preserve the draft, and derived-artifact regeneration is only an explicit recorded request; no worker or generated completion is claimed. SAX-045 shows download availability for the concrete revision currently displayed.

## Play the original audio with revision events

```text
/transcriptions/{job_id}/review/playback
```

SAX-044 implements RF-053 with this explicit interpretation:

```text
original audio selected locally and played by the browser
+
visual cursor and latest-revision events synchronized to media currentTime
```

It does not synthesize MIDI or play MIDI, MusicXML, SVG, or any generated artifact.

### Initial data

The route loads only through Spring Boot by reusing:

```text
getTranscription
getTranscriptionRevisionHistory
getTranscriptionRevision
```

It loads job metadata, revision history, and the latest revision detail once. There is no review polling and no direct FastAPI call.

### Reselect the original file

The current services do not store or expose original audio bytes. The user must select the original `.mp3` or `.wav` again after entering or reloading the playback route.

The browser verifies identity using:

```text
file.size === job.size_bytes
SHA-256(file bytes) === job.audio_sha256
```

Size is checked before reading and hashing. SHA-256 is calculated with Web Crypto and converted to lowercase 64-character hexadecimal. Filename is not treated as identity: a renamed matching file is accepted, while same-name content with a different digest is rejected.

The verification path does not call `fetch`, create `FormData`, send a POST, or log bytes, digest material, or object URLs. Missing Web Crypto and replacement races produce controlled outcomes.

### Object URL and privacy

Only a verified file receives one local object URL. It is revoked on replacement, unmount, stale completion, or media failure. It is not persisted or exposed.

The interface states:

```text
The selected file stays in this browser session.
It is used only through a local object URL.
It is not uploaded again.
```

No server is claimed to retain the audio.

### Native playback and synchronization

The player is native:

```html
<audio controls preload="metadata"></audio>
```

There is no autoplay. Native controls remain visible and default pitch/speed are unchanged.

`HTMLMediaElement.currentTime` is authoritative. While playing, one `requestAnimationFrame` loop updates the visual cursor. Pause, ended, error, replacement, and unmount stop and cancel it. `timeupdate`, `seeking`, and `seeked` correct state immediately.

An event is active exactly when:

```text
onset_seconds <= currentTime < offset_seconds
```

All overlapping active events remain marked and API order is preserved. Active state is textual, not color-only. Human events keep confidence unavailable rather than receiving an invented value.

Before media metadata, maximum event offset is the timeline fallback. A finite positive decoded duration replaces it after `loadedmetadata`. Events beyond the audio duration remain visible and produce a warning; source onset/offset values are not truncated.

Every event exposes a keyboard-operable `Seek to note` action. It moves `audio.currentTime` to onset and updates the cursor without starting playback.

`Reload latest revision` manually reloads history and detail while preserving the already verified local audio and object URL. It does not poll, autoplay, restart, or reset current time in application code. SAX-045 renders downloads for that loaded revision independently from the audio object URL.

## Download revision artifacts

The reusable `Revision artifact downloads` panel is mounted from:

```text
/transcriptions/{job_id}/review
/transcriptions/{job_id}/review/edit
/transcriptions/{job_id}/review/playback
```

The browser calls only Spring Boot. Supported descriptors are exactly:

```text
MIDI     audio/midi                                  .mid
MusicXML application/vnd.recordare.musicxml+xml      .musicxml
SVG      image/svg+xml                               .svg
```

`getRevisionArtifacts` validates exact fields, requested/returned job and revision identity, safe unique IDs and filenames, deterministic order, positive sizes, lowercase SHA-256, and type/media/extension compatibility. PDF descriptors are rejected and no PDF button is rendered.

`downloadRevisionArtifact` first obtains the authoritative descriptor through Spring, then validates the binary response's status, `Content-Type`, safe exact `Content-Disposition`, optional `Content-Length`, digest header, actual `ArrayBuffer` size, and SHA-256 calculated through Web Crypto. A `Blob` is returned only when every check matches.

After validation, the browser:

1. creates a `Blob` with the exact media type;
2. creates a separate temporary artifact object URL;
3. creates a hidden temporary link with `download=filename`;
4. clicks it;
5. removes the link;
6. revokes the URL in `finally`.

The artifact URL is never reused as the SAX-044 audio URL. `window.open`, localStorage, IndexedDB, Cache API, cookies, and service workers are not used.

States are explicit:

```text
loading
available
not_ready
downloading
downloaded
error
```

An existing revision without a registered bundle displays:

```text
Artifacts are not available for this revision yet.
```

Each available descriptor shows type, filename, size, abbreviated SHA, full technical SHA, and a keyboard-operable button whose accessible name includes type and filename. Loading/downloading/success use polite live status; errors use a focused alert; the initiating button retains focus after success.

The interface states:

```text
Downloads are retrieved through the Saxo product API.
No public storage URL is exposed.
```

No permanence or retention is claimed.

MIDI, MusicXML and SVG download transport is implemented for registered artifacts. Artifact generation from a normal uploaded job remains pending. PDF is not implemented.

## Accessibility and responsive layout

- one route `h1`;
- semantic tables, visible labels, native audio controls, and a clear downloads landmark;
- polite live regions for loading, verification, download, and success;
- `role="alert"` and programmatic focus for errors and conflicts;
- accessible seek and download button names;
- active/download state communicated with text and structure, not color alone;
- keyboard operation and visible focus;
- horizontally scrollable tables and timelines;
- responsive actions, file selection, and artifact rows;
- no autoplay or mandatory animation;
- reduced-motion styles;
- no emoji or blue primary treatment.

## Boundaries

SAX-044 does not include direct FastAPI calls, audio upload from playback, server audio endpoints, audio persistence, PostgreSQL, object storage, signed URLs, localStorage, IndexedDB, cookies, service workers, offline cache, MIDI player or synthesis, Web Audio synthesizer, SoundFont, waveform, spectrogram, artifact playback, audio editing, speed/pitch controls, loops, metronome, score following, MusicXML/SVG interaction, worker, queue, BackgroundTasks, WebSocket, SSE, review polling, authentication, or analytics.

SAX-045 does not include PDF, ZIP, bulk download, artifact generation from GET, regeneration execution, automatic upload processing, artifact persistence, public storage URLs, authentication/authorization, retention, artifact playback, WebSocket, SSE, polling, or SAX-050.

Documentation:

- [`docs/contracts/audio-upload-ui-v1.md`](docs/contracts/audio-upload-ui-v1.md)
- [`docs/contracts/job-progress-ui-v1.md`](docs/contracts/job-progress-ui-v1.md)
- [`docs/contracts/transcription-review-ui-v1.md`](docs/contracts/transcription-review-ui-v1.md)
- [`docs/contracts/transcription-revision-editor-v1.md`](docs/contracts/transcription-revision-editor-v1.md)
- [`docs/contracts/synchronized-local-playback-v1.md`](docs/contracts/synchronized-local-playback-v1.md)
- [`docs/contracts/revision-artifact-download-ui-v1.md`](docs/contracts/revision-artifact-download-ui-v1.md)
- [`docs/tdd/iteration-001.md`](docs/tdd/iteration-001.md)
- [`docs/tdd/iteration-002.md`](docs/tdd/iteration-002.md)
- [`docs/tdd/iteration-003.md`](docs/tdd/iteration-003.md)
- [`docs/tdd/iteration-004.md`](docs/tdd/iteration-004.md)
- [`docs/tdd/iteration-005.md`](docs/tdd/iteration-005.md)
- [`docs/tdd/iteration-006.md`](docs/tdd/iteration-006.md)
