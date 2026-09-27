# TDD iteration 005 — Synchronized local playback

## Story and requirement

```text
SAX-044 — Synchronized playback
RF-053 — The user can listen to audio and result synchronized
```

Scope interpretation:

```text
original local audio playback
+
visual latest-revision cursor/events synchronized to HTMLMediaElement.currentTime
```

No MIDI synthesis, artifact playback, waveform, re-upload, IA change, or Backend change is included.

## Exact base

Frontend SAX-043 was squash-merged as:

```text
717cd77204cf69e2f3a4a7cb9dcc3d8e457ee837
SAX-043: Add revision-based note editor
```

SAX-044 branch:

```text
feature/SAX-044-synchronized-playback
```

IA and Backend mains were independently verified at their SAX-043 squash commits and received no SAX-044 branch or functional change.

## RED

Tests were committed before their production contracts:

```text
8f582b1 test(SAX-044): define local audio identity verification
29bd318 test(SAX-044): define synchronized playback timeline
2413c78 test(SAX-044): define synchronized playback states and errors
bde234b test(SAX-044): define object URL and frame lifecycle
ccecab3 test(SAX-044): define playback navigation from review and editor
```

Protected workflow evidence:

```text
Quality #88
run: 29950362809
job: 89026238449
head: ccecab3437e28131b508bed846e84cdef8787a1e
status: failure expected
```

Checkout, Node 24.18.0, pinned npm, and `npm ci` succeeded. Vitest failed because these production modules and links did not yet exist:

```text
src/lib/local-audio-verification.ts
src/lib/playback-synchronization.ts
src/components/transcription-synchronized-playback.tsx
Play synchronized review links
```

The failure was therefore functional RED rather than installation or dependency failure.

## GREEN

Minimal production was added in this order:

```text
8daad81 feat(SAX-044): add local audio verification
cd81c8b feat(SAX-044): add playback synchronization helpers
3768f02 feat(SAX-044): add synchronized playback route component
fb4984c feat(SAX-044): add synchronized playback route
35b6f9a feat(SAX-044): style synchronized local playback
93fc07d feat(SAX-044): load synchronized playback styles
783881c feat(SAX-044): link review to synchronized playback
580dfb4 feat(SAX-044): link editor to synchronized playback
```

Implemented behavior:

- visible local MP3/WAV selection;
- size check before content read/hash;
- Web Crypto SHA-256 lowercase verification;
- renamed-file acceptance and mismatched-content rejection;
- abort/stale-selection protection;
- object URL only after verification;
- one active URL and deterministic revocation;
- native non-autoplay `<audio controls preload="metadata">`;
- latest job/history/revision loading through Spring clients;
- media currentTime as authoritative clock;
- one requestAnimationFrame loop;
- immediate media/seek corrections;
- onset-inclusive and offset-exclusive active-event rule;
- simultaneous overlapping active events;
- event-order preservation;
- real-duration replacement of maximum-offset fallback;
- warning without truncation for events beyond audio duration;
- seek-to-note without play;
- manual latest-revision reload preserving local audio;
- explicit error, privacy, and accessibility behavior.

An intermediate protected run demonstrated the full functional suite:

```text
164 tests passed
93.35% statements
91.37% branches
97.39% functions
95.66% lines
```

It then stopped at Prettier, so it was not treated as the final quality result.

## REFACTOR

The first GREEN run exposed a real lifecycle problem: inline default media/frame functions changed identity on render, causing cleanup to abort valid verification. Production was refactored to stable module-level defaults:

```text
80c22a1 refactor(SAX-044): centralize media and frame lifecycle
```

Tests were then made deterministic by awaiting the asynchronous initial load and resolving controlled promises inside React `act`:

```text
749e8ac test(SAX-044): make media state tests deterministic
e781f94 test(SAX-044): await loaded playback fixtures
```

The editor was reconstructed without behavioral changes except the explicit playback link. Existing SAX-043 editor tests remained green.

No coverage threshold, inclusion rule, TypeScript strictness, lint rule, or quality workflow was weakened. Temporary formatting diagnostics, when used, must be removed before the final tree.

## Test matrix

### Local verification

- MP3/WAV and uppercase extensions;
- empty and unsupported files;
- size mismatch before read/hash;
- known SHA-256 synthetic bytes;
- renamed matching file;
- same name with mismatched content;
- unavailable Web Crypto;
- abort before and after digest;
- replacement during verification;
- stale completion ignored;
- no fetch, FormData, or console disclosure.

### Object URL

- creation only after successful hash;
- no creation before verification;
- revocation on replacement;
- revocation on unmount;
- revocation after media error;
- only one active URL;
- mismatch retains no URL.

### Playback and synchronization

- native controls and no autoplay;
- loaded metadata, play, pause, ended, timeupdate, seeking, seeked, media error;
- current time and duration text;
- maximum-offset fallback and real media duration;
- cursor updates;
- one animation frame loop;
- pause/end/unmount cancellation;
- exact onset/offset boundary rule;
- overlapping active events;
- out-of-duration warning without source mutation;
- seek without automatic playback;
- model confidence preserved and human confidence not invented.

### API and revisions

- job metadata;
- revision history;
- latest revision detail;
- not-ready, not-found, and Backend errors;
- manual latest reload;
- verified audio preserved during reload;
- no polling;
- no direct FastAPI call.

### Accessibility

- one heading;
- visible label;
- polite live verification;
- focused alerts;
- accessible seek buttons;
- textual time and active state;
- keyboard controls;
- no color-only state;
- reduced-motion styles;
- responsive horizontal timeline.

## Traceability

```text
SAX-044
→ RF-053
→ verifyLocalAudioFile tests
→ native media lifecycle tests
→ playback synchronization helper tests
→ timeline/seek/overlap component tests
→ navigation and accessibility tests
```

## Boundaries

No audio was committed, uploaded from playback, persisted, or exposed by a new server endpoint. No MIDI synthesis/player, Web Audio synthesizer, SoundFont, waveform, spectrogram, download, artifact playback, speed/pitch control, loop, metronome, score following, worker, queue, BackgroundTasks, WebSocket, SSE, polling, authentication, analytics, SAX-045, IA change, or Backend change was implemented.
