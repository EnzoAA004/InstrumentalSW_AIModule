# Transcription revision editor — v1

## Objective

SAX-043 adds an accessible, reloadable editor for immutable transcription revisions. The browser calls only the Spring Boot product API, validates the local draft immediately, and saves one explicit operation batch.

```text
/transcriptions/{job_id}/review/edit
→ Spring Boot
→ FastAPI revision API
```

The existing SAX-042 read-only review remains available and links to the editor through `Edit notes`.

## Loading model

The editor loads exactly:

1. revision history;
2. the latest revision detail;
3. editable draft events copied from that server revision.

It performs no review polling, autosave, background synchronization, WebSocket, or SSE. The UUID remains in the route, so reload requires no browser storage.

State remains separated:

```text
history
serverRevision
draftEvents
validationErrors
saveState
selectedRevision
```

Fetched objects are not mutated. Stable event IDs are React keys.

## Editable fields

The latest revision permits editing:

```text
written_pitch_midi
onset_seconds
offset_seconds
```

Existing velocity and confidence are read-only. A new event receives editable initial values and velocity 64 by default.

Concert MIDI is displayed immediately from:

```text
written_pitch_midi - saxophone offset
```

The browser never sends an independent concert pitch.

## Immediate validation

Before any POST, the editor validates:

- non-empty unique event ID;
- supported model/human origin;
- written MIDI required, integer, and `0..127`;
- derived concert MIDI `0..127`;
- onset required, finite, and non-negative;
- offset required, finite, and greater than onset;
- new-event velocity required, integer, and `0..127`.

Inline errors are connected with `aria-describedby`, invalid inputs use `aria-invalid`, and an error summary uses `role="alert"`. `Save revision` remains disabled while the draft is invalid or unchanged.

Spring and FastAPI validate the command again; client validation is not authoritative.

## Local operations

The editor supports:

```text
update written pitch/onset/offset
add note
delete note with confirmation
discard local changes
save revision
```

Operations are derived by comparing the validated draft with `serverRevision`:

- missing original ID → delete;
- changed original values → update;
- draft-only event → add;
- unchanged event → no operation.

One explicit POST is sent only when the user activates `Save revision`. No request is sent per keystroke.

## Human events

Human draft events display:

```text
Human-added event
Confidence: Not applicable
Confidence status: Human edit
```

They never display 0%, 100%, or invented model confidence. After a successful save, the server-assigned `human-{UUID}` ID replaces the local draft-only key.

## History

The accessible `Revision history` selector displays:

```text
Revision 0 — original
Revision 1
Revision 2
...
```

Only the latest revision is editable. Selecting an older revision loads its exact detail and disables edit controls. Historical revisions are never changed in place.

## Optimistic conflict

A `409 REVISION_CONFLICT`:

- keeps the local draft values;
- focuses and displays the conflict alert;
- offers `Reload latest revision`;
- performs no silent overwrite.

Reloading is explicit and then replaces the draft with the newly fetched latest revision.

## Derived artifacts

A saved revision displays:

```text
Derived artifacts are stale.
```

The explicit button is:

```text
Request artifact regeneration
```

After HTTP 202 the editor displays:

```text
Regeneration requested.
No processing worker is connected yet.
```

The interface does not display completed, MIDI regenerated, score regenerated, progress, percentage, or ETA. It receives no artifact bytes and offers no download.

Editing, validation and revision history are implemented.

A regeneration request is recorded explicitly.

Artifact execution remains pending.

## Accessibility and responsive behavior

- one `h1`;
- visible revision label;
- semantic table;
- visible input labels through accessible names;
- inline errors associated with inputs;
- alert summaries and programmatic focus;
- explicit delete and confirm-delete buttons;
- keyboard-operable history, links, and actions;
- visible focus;
- origin, errors, stale state, and request state communicated by text rather than color alone;
- horizontally scrollable table;
- responsive action layout;
- no blue primary treatment, emoji, or mandatory animation.

## Boundaries

No direct FastAPI call, autosave, polling, real-time collaboration, historical mutation, confidence editing, existing-velocity editing, audio/MIDI playback, waveform, synchronization, real artifact generation, download, authentication, SAX-044, or later story is included.
