# TDD iteration 004 — SAX-043 revision-based note editor

## Scope

This iteration implements only the browser-facing SAX-043 editor over the Spring Boot revision gateway.

```text
/transcriptions/{job_id}/review/edit
```

The browser calls Spring Boot only. It does not call FastAPI directly and does not execute artifact generation.

## RED

Tests were committed before production code for:

- typed history, detail, revision-create, and regeneration-request clients;
- exact Backend methods, paths, JSON bodies, and status codes;
- response identity and complete payload validation;
- copying a server revision into a separate local draft;
- written-to-concert MIDI derivation for every saxophone type;
- immediate pitch, timing, velocity, origin, and identity validation;
- update, add, delete, discard, and explicit save behavior;
- immutable historical revision display;
- `409 REVISION_CONFLICT` with draft preservation;
- explicit reload of the latest revision;
- human confidence shown as not applicable;
- regeneration-request messaging without a completion claim;
- accessible labels, inline errors, alert focus, keyboard controls, and responsive overflow;
- absence of autosave, polling, direct FastAPI calls, playback, downloads, worker, or artifact bytes.

Representative tests-only commits:

```text
e2472708a86dafd12db86605f35f80b60b569f66
c5d01bde51f554f47fa1607309784e40a9e5da5f
566c343fa4cbc469b1841bc5aafa41f13f1af604
```

The first protected quality run failed because the typed client, route, and editor did not yet exist. Dependency installation succeeded, so the failure represented the intended RED state.

## GREEN

The minimum production implementation added:

- `src/lib/transcription-revisions.ts`;
- `src/components/transcription-revision-editor.tsx`;
- the dynamic edit route;
- the read-only review link;
- responsive editor styles.

The client validates every successful response and maps stable public errors. The editor keeps `serverRevision` and `draftEvents` separate, derives one explicit operation batch, and sends it only when the user activates `Save revision`.

Representative implementation commits:

```text
cdb76ea1f37136af10d9e95e5af9d9651e9932ec
5fa106a7c9f8a7e38f004d4fb0c3556a2466835f
d851ea4de26ece1b5a979a3d79bc961c6391c593
cdae72cd7691aec28f0aa67b7f30e1ceda8c7f83
19b80c868d9d302ee24ed2b32bf58f57066834a6
```

## REFACTOR

The refactor phase preserved behavior while improving:

- deterministic test assertions for repeated model-event labels;
- asynchronous focus assertions for accessible error states;
- branch coverage for malformed responses and error paths;
- conflict, regeneration, and reload error coverage;
- Prettier formatting across source, tests, and documentation.

No threshold was lowered and no SAX-043 source was excluded from coverage.

## Resulting behavior

The editor:

1. loads history and the latest revision;
2. copies events into a local draft;
3. validates on every edit;
4. derives concert MIDI from written MIDI;
5. supports update, add, delete, and discard;
6. saves one immutable child revision;
7. loads old revisions read-only;
8. preserves the draft on conflict;
9. records an explicit regeneration request.

Human-added events receive a server identity after save and never claim model confidence.

## Quality gate

The final evidence must come from `npm run quality` on the documentation-complete head and includes:

```text
Vitest
coverage >= 90% statements
coverage >= 90% branches
coverage >= 90% functions
coverage >= 90% lines
ESLint
Prettier
TypeScript strict
Next.js production build
```

Earlier implementation evidence reached 126 passing tests and exceeded every 90% coverage threshold. That run is not reused as final evidence after this documentation change; the protected gate is rerun on the definitive head.

## Boundaries

There is no autosave, review polling, WebSocket, SSE, direct FastAPI call, historical mutation, playback, waveform, download, worker, queue, BackgroundTasks, or generated MIDI, MusicXML, or SVG bytes.

Editing, validation and revision history are implemented.

A regeneration request is recorded explicitly.

Artifact execution remains pending.
