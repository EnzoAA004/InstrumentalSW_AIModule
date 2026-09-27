# TDD iteration 003 — SAX-042 note review UI

## Scope

Visualize exact note/timing/confidence data already available through the product Backend, without polling the review or inventing output.

Base and branch:

```text
8b497369707704f352838650eac3ccb92fcc3c40
feature/SAX-042-note-review-view
```

## RED

Tests preceded production:

```text
cec705 test(SAX-042): define typed transcription review client
a8985 test(SAX-042): define accessible note table timeline and errors
518f9b test(SAX-042): define review navigation from progress
```

They referenced the review type/client, component, route, timeline, table, state model, and navigation before those modules existed. The normal quality run therefore failed for missing SAX-042 code rather than dependency installation.

## GREEN

Production added:

- complete `TranscriptionReview` and event types;
- one-shot validated Backend GET client;
- reloadable dynamic review route;
- `View notes` navigation from progress;
- loading/ready/empty/not-ready/not-found/error states;
- horizontally scrollable HTML/CSS timeline;
- semantic event table;
- textual, visual, patterned, and accessible low-confidence markers;
- abort-on-unmount behavior and safe error rendering.

## REFACTOR

Validation is centralized in `transcription-api.ts`; review layout/formatting is centralized in the review component. Tests distinguish offset from derived duration and inspect roles, rows, timeline items, data attributes, and accessible text instead of snapshots. Pinned Prettier output was obtained through a temporary read-only diagnostics workflow, then the workflow was removed.

## Tests

Coverage includes:

- valid and invalid UUID;
- exact Backend URL and absence of FastAPI URL;
- HTTP 200, 400, 404, 409, 502;
- network failure and abort;
- malformed JSON, unknown versions, UUID mismatch, inconsistent summary, bad indices/events;
- progress navigation;
- loading, ready, empty, not-ready, not-found, and error;
- one/multiple and overlapping events;
- timeline origin/order/position metadata;
- derived duration;
- low-confidence text/class/ARIA;
- complete semantic table;
- absence of editing, playback, refresh, and polling controls in the review;
- all SAX-040/SAX-041 regressions.

## Quality

Definitive functional head before documentation:

```text
f798c9f49bc4911b149c47435664941efdce8e41
Quality #66
run 29879466998
Node 24.18.0
npm 11.6.2
84 tests passed
92.47% statements
90.46% branches
96.77% functions
92.95% lines
ESLint passed
Prettier passed
TypeScript strict passed
Next.js production build passed
```

The final documentation head is revalidated by the same protected workflow and recorded in the draft PR.

## Boundaries

No synthetic notes, direct FastAPI call, review polling, editing, deletion, regeneration, playback, waveform, synchronization, SVG/PDF, download, storage, authentication, SAX-043, or later story was introduced.
