# Synchronized local playback contract — v1

## Traceability

```text
SAX-044
→ RF-053
→ local audio SHA-256 verification
→ native HTML audio playback
→ revision event synchronization
→ synchronized cursor and active events
→ Frontend tests
```

Priority: P1. Estimate: 8 points.

## Scope decision

For SAX-044, “audio and result synchronized” means:

```text
original audio selected locally and played by the browser
+
visual cursor and latest-revision events synchronized to media currentTime
```

It does not mean MIDI synthesis, note-generated audio, MIDI/MusicXML/SVG playback, waveform display, or mixing original and synthesized audio.

## Architecture

The route is:

```text
/transcriptions/{job_id}/review/playback
```

Initial data is loaded only through the Spring Boot product API by reusing:

```text
getTranscription
getTranscriptionRevisionHistory
getTranscriptionRevision
```

The browser never calls FastAPI directly. There is no review polling.

The route loads:

1. job metadata, including `size_bytes` and `audio_sha256`;
2. immutable revision history;
3. the detail of the latest revision.

## Why the user reselects the file

The current system does not retain or expose original audio bytes. SAX-044 does not add a server audio endpoint, storage, object storage, signed URL, database, or cache. The user therefore selects the original MP3/WAV again in the playback route.

Reloading the page requests the local file again. The file is not carried through hidden navigation state and is not placed in localStorage, IndexedDB, cookies, a service worker, or an offline cache.

## Local selection

The visible control is labeled:

```text
Select original audio
```

It accepts `.mp3` and `.wav` case-insensitively. Empty and unsupported files are rejected before hashing. Replacing the selection cancels or invalidates the previous verification and releases any prior object URL.

## Identity verification

The local helper verifies in this order:

1. supported extension;
2. non-empty file;
3. exact `file.size === size_bytes`;
4. SHA-256 through Web Crypto;
5. lowercase 64-character hexadecimal comparison with `audio_sha256`.

Filename is not part of the content identity. A renamed file is accepted when size and digest match. A file with the same name and size is rejected when the digest differs.

No alternate hash is used. Missing Web Crypto produces a controlled error. Abort checks before and after asynchronous work, plus a monotonically increasing selection sequence, prevent obsolete results from replacing a newer selection.

The verification utility does not call `fetch`, create `FormData`, send a POST, log file bytes, log the object URL, or log intermediate/final hash material.

## Local object URL

Only after successful size and SHA-256 verification does the browser call:

```text
URL.createObjectURL(file)
```

At most one object URL remains active. It is revoked:

- when a verified file is replaced;
- when the route unmounts;
- when a later media decoding error makes it unusable;
- when a stale completion creates an URL that must not become active.

The URL is not persisted, published, returned by an API, included in errors, or written to logs.

## Privacy statement

The interface states:

```text
The selected file stays in this browser session.
It is used only through a local object URL.
It is not uploaded again.
```

The server is not claimed to retain the audio.

## Native media playback

After verification, the route renders:

```html
<audio controls preload="metadata"></audio>
```

There is no autoplay. Playback requires user action and native controls remain available. Pitch and playback speed are not modified.

Handled events:

```text
loadedmetadata
play
pause
timeupdate
seeking
seeked
ended
error
```

Current time and decoded duration are displayed as text. A decoding failure removes the unusable object URL and shows:

```text
The browser could not decode this audio file.
```

## Authoritative clock and cursor

`HTMLMediaElement.currentTime` is the authoritative time source. While playing, one `requestAnimationFrame` loop reads it and moves the visual cursor. A second concurrent loop is never created.

The loop stops and its pending frame is cancelled on pause, ended, media error, replacement, and unmount. `timeupdate`, `seeking`, and `seeked` update the cursor and active events immediately.

The cursor has an accessible description but is not a live region, preventing a screen reader announcement on every frame. Current time remains available as normal text.

## Event activation

An event is active exactly when:

```text
onset_seconds <= currentTime < offset_seconds
```

All overlapping events satisfying that condition are active simultaneously. API order is preserved. Active state uses explicit text (`Active now`) and structural styling rather than color alone.

Model confidence is retained exactly. Human events continue to expose `confidence: null` and do not receive invented confidence.

## Timeline duration

Before metadata, the visual duration is the maximum revision-event offset, with a technical minimum of one second for an empty timeline.

After `loadedmetadata`, a finite positive media duration replaces that fallback. Event onset and offset are never changed or truncated. Events whose offset exceeds decoded duration remain visible and produce an incompatibility warning.

## Seek to note

Every event exposes a keyboard-operable action:

```text
Seek to note
```

It assigns the event onset to `audio.currentTime` and updates the cursor immediately. It does not call `play`, does not enable autoplay, and does not make the timeline editable. Written MIDI, concert MIDI, onset, offset, origin, and confidence status remain visible.

## Revision selection

Playback uses the latest revision available during initial loading and displays:

```text
Revision N
```

There is no polling for revisions created elsewhere. `Reload latest revision` explicitly reloads history and latest detail. The already verified local audio and object URL remain attached, playback is not started or restarted automatically, and current time is not reset by application code.

## UI states

```text
loading
awaiting_audio
verifying_audio
ready
playing
paused
ended
mismatch
media_error
api_error
```

Required messages include:

```text
Select the original MP3 or WAV used for this transcription.
Verifying audio content…
Audio verified locally. The file was not uploaded.
This file does not match the transcription job.
The browser could not decode this audio file.
```

Not-ready, not-found, and Backend failures use the existing controlled API envelopes.

## Accessibility and responsive behavior

- one route `h1`;
- visible selector label;
- polite verification live region;
- focused `role="alert"` errors;
- accessible event seek names;
- textual current time, playback state, and active state;
- keyboard-native audio and button controls;
- visible focus;
- no autoplay;
- no color-only status;
- horizontally scrollable timeline;
- responsive navigation and selection layout;
- no mandatory CSS transition;
- `prefers-reduced-motion` explicitly disables transitions;
- no emoji or blue primary treatment.

## Tests

Tests use only synthetic bytes created in memory. They mock native media behavior, `requestAnimationFrame`, object URLs, and Web Crypto where appropriate. One helper test calculates the known SHA-256 of synthetic `abc` bytes through a real Web Crypto implementation.

Coverage includes local identity, replacement races, object URL lifecycle, media events, cursor, overlap activation, boundary timing, duration fallback, out-of-range events, seek, manual revision reload, errors, accessibility, no polling, and navigation.

## Limitations and exclusions

SAX-044 does not implement:

- storage or retrieval of audio bytes;
- audio upload from the playback route;
- IA or Backend changes;
- MIDI player or synthesis;
- Web Audio synthesizer or SoundFont;
- waveform or spectrogram;
- artifact playback or download;
- speed/pitch controls, loops, metronome, or score following;
- MusicXML or SVG interaction;
- offline persistence;
- worker, queue, BackgroundTasks, WebSocket, SSE, or polling;
- authentication or analytics;
- SAX-045.
