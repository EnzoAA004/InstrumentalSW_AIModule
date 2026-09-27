# Transcription review UI — v1

## Purpose

SAX-042 adds a reloadable, read-only Next.js view for an already-produced transcription review.

```text
/transcriptions/{job_id}/review
→ Spring Boot GET /api/v1/transcriptions/{job_id}/review
→ FastAPI authoritative review snapshot
```

The browser never calls FastAPI directly and performs no review polling.

## Navigation

The existing progress page retains its refresh, pause/resume, and back controls and adds `View notes`, linking to `/transcriptions/{job_id}/review`. The UUID lives in the route, so reload requires no localStorage, sessionStorage, or cookie.

## Typed client

```typescript
getTranscriptionReview(jobId, signal?)
```

The client validates UUID before fetch, safely encodes the path segment, sends one bodyless GET to the Backend, accepts only HTTP 200, validates the complete payload and requested/returned UUID identity, maps public 400/404/409/502 envelopes, preserves abort behavior, and performs no retry or polling.

## States

```text
loading
ready
empty
not_ready
not_found
error
```

A 200 response with zero events shows `No note events were produced.` A 409 response shows `Transcription notes are not available yet.` These states are intentionally different; no empty or synthetic result represents not-ready work.

## Timeline

The HTML/CSS timeline:

- starts at zero;
- uses the maximum `offset_seconds` as its visual duration;
- derives each event width from `offset_seconds - onset_seconds`;
- preserves API order;
- keeps overlapping events as separate rows;
- allows horizontal scrolling;
- renders written/concert MIDI and confidence status;
- does not represent audio, playback, measures, meter, or quantization.

Raw numeric values are retained by the typed review. Formatting for display does not mutate them.

## Low confidence

Every event remains visible. A low-confidence event uses multiple cues:

- text `Low confidence`;
- a dashed border;
- a patterned background;
- an accessible `aria-describedby` reference.

The view states: `Confidence is a model signal, not calibrated accuracy.` Confidence remains a number in `0..1`; it is not converted to a percentage.

## Semantic alternative

A table exposes all events with:

```text
Index
Written MIDI
Concert MIDI
Onset
Offset
Duration
Velocity
Confidence
Confidence status
```

Duration is derived only in the UI. The API has no `duration_seconds` field.

## Accessibility and responsive behavior

The route has one `h1`; loading/summary text uses polite live regions; errors use `role="alert"` and receive focus; UUID and technical values wrap; controls and links are keyboard operable with visible focus. Timeline and table scroll horizontally while narrow layouts retain readable single-column navigation. No status depends only on color, and there is no mandatory animation, emoji, or blue primary treatment.

## Exclusions

No editing, deletion, note creation, regeneration, history, review polling, audio/MIDI player, waveform, synchronization, SVG/PDF, download, storage, authentication, SAX-043, or later story is included.
