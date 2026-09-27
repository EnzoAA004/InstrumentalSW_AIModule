# Next implementation agent prompt

Use this prompt with Claude Code, Codex, or another repository-capable coding agent.

---

You are continuing the Saxo project in the single canonical GitHub repository:

```text
EnzoAA004/InstrumentalSW_AIModule
```

Do not create another repository and do not make new product changes in the old repositories `InstrumentalSW_Backend` or `InstrumentalSW_Frontend`.

## Repository branch topology

- AI/FastAPI stable: `main`
- AI stable migration snapshot: `component/ai`
- Spring Boot Backend: `component/backend`
- Next.js Frontend: `component/frontend`
- current AI WIP: `feature/SAX-036-monophonic-end-to-end-processor`, PR #29

For new work:
- AI branches start from `main` and merge to `main`;
- Backend branches start from `component/backend` and merge to `component/backend`;
- Frontend branches start from `component/frontend` and merge to `component/frontend`.

Never merge Backend or Frontend source trees into `main`; the project intentionally keeps the three build roots separated by branches inside one repository.

Read before coding:
- `docs/project/repository-consolidation.md`
- `docs/project/implementation-checklist.md`
- existing `docs/contracts/**`
- existing `docs/tdd/**`
- project README on the relevant component branch.

Follow TDD: RED → GREEN → REFACTOR. Do not weaken tests merely to make CI green.

## Goal

Finish the first operational monophonic Saxo MVP end to end:

```text
Next.js
  → Spring Boot
  → FastAPI upload
  → durable original audio
  → PostgreSQL queue
  → worker
  → canonical WAV
  → FiloSax monophonic transcription
  → post-processing/confidence/transposition
  → tempo + rhythm quantization
  → MIDI + MusicXML + SVG
  → persisted review/revision
  → Backend gateway
  → Frontend review/edit/download
```

The MVP is isolated monophonic saxophone. Do not start source separation, multiinstrument classification or multi-track scoring until the monophonic MVP is complete.

## Phase 1 — Finish SAX-036 / PR #29

Continue the existing branch and PR rather than starting a duplicate implementation.

Current known blockers:
1. run Ruff formatting on the files reported by CI;
2. the Python 3.11 real-baseline E2E currently ends with zero final written-pitch events for the generated saxophone-like fixture.

Investigate the second blocker rather than skipping it. Determine whether:
- FiloSax produces no raw notes after FFmpeg canonicalization;
- raw notes exist but the post-processing minimum-duration policy removes them;
- the generated signal is not a representative full-pipeline fixture.

Keep a real baseline E2E. Use only generated audio or a small audio fixture whose rights permit repository storage. The test must prove that a valid input can produce revision zero plus MIDI, MusicXML and at least one SVG page.

Preserve the intended controlled behavior:
- insufficient tempo evidence uses the explicit fallback tempo;
- corrupt/undecodable input is terminal and does not consume transient retries;
- a controlled SVG-render failure preserves valid MIDI and MusicXML;
- stale queue claims cannot overwrite a newer claim.

Run the complete AI quality gate and require all supported Python jobs to pass before merging PR #29.

## Phase 2 — SAX-076: durable review/revision/regeneration persistence

Implement PostgreSQL-backed repositories for:
- transcription review source/result;
- immutable transcription revisions and events;
- regeneration requests.

Requirements:
- Alembic migrations;
- no JSON blob shortcut if it removes useful integrity/concurrency constraints;
- atomic creation of source review + revision zero;
- sequential immutable revisions;
- stale writers rejected;
- idempotent regeneration request semantics;
- API process and worker process must share state;
- state survives process restart.

Preserve current public API contracts and error codes unless there is a documented versioned reason to change them.

## Phase 3 — SAX-077: production composition and worker process

Build an explicit production composition root.

FastAPI process must use configured:
- PostgreSQL job/review/revision/regeneration repositories;
- private S3-compatible object storage;
- PostgreSQL processing queue.

Worker process must use the same durable resources and:
- `TranscriptionWorker`;
- the concrete monophonic processor from SAX-036;
- bounded retry;
- lease/reclaim semantics;
- clean shutdown;
- configuration validation.

Provide a simple executable/CLI/container entry point for running the worker separately from the HTTP API.

Development/test in-memory adapters may remain, but production composition must not silently fall back to them.

## Phase 4 — execute regeneration of edited revisions

The current API can record a regeneration request, but recording is not enough.

Implement worker-side execution so an edited immutable revision can regenerate the derived artifacts for that exact revision:
- MIDI;
- MusicXML;
- SVG where rendering succeeds.

Update `derived_artifacts_status` consistently and prevent revision N artifacts from being attached to revision M.

Keep old revision artifacts immutable.

## Phase 5 — SAX-078: cross-component E2E

Use the three canonical branches.

Verify the real product flow:
1. Frontend uploads MP3/WAV and saxophone type.
2. Spring Boot forwards the request to FastAPI.
3. API responds asynchronously with job ID.
4. Frontend polls status through Backend.
5. Worker processes the durable job.
6. Review appears.
7. User can edit a note and create a new immutable revision.
8. Regeneration executes.
9. User can download MIDI, MusicXML and SVG through Backend.
10. Restarting API/worker does not lose job/review/revision state.

Add automated contract/E2E tests where practical. Do not put private datasets, credentials or checkpoints directly in Git.

## Phase 6 — operational MVP requirements

Then implement, in this order:
- SAX-073 authentication and authorization;
- SAX-074 structured logs, job/request correlation and basic metrics;
- SAX-075 retention and deletion policy.

Keep uploaded audio private. No public object-storage URL should be required by the browser.

## Phase 7 — model evaluation before training

Complete SAX-054 before SAX-055.

Use the existing:
- dataset provenance registry;
- reproducible FiloSax preparation;
- leakage-safe splits;
- AMT metrics.

Compare the current pinned baseline against any serious candidate using the same versioned evaluation data and metrics. Record results and failure categories.

Only fine-tune/train a specialized model (SAX-055) if the measured result justifies it. Then write/update the internal model card (SAX-056).

## Explicitly deferred

Do not begin these until the monophonic MVP above is green and usable:
- SAX-060 sax/other dataset;
- SAX-061 source separation;
- SAX-062 chained source-separation evaluation;
- SAX-080 instrument classification;
- SAX-081 multi-stem/multi-engine orchestration;
- SAX-082 multi-track score.

## Quality requirements

AI:
- run the repository quality command;
- pytest coverage >= 90%;
- Ruff lint;
- Ruff format;
- strict mypy;
- real FiloSax integration on its supported CI job.

Backend:
- from `component/backend`, run `./mvnw --batch-mode --no-transfer-progress verify`.

Frontend:
- from `component/frontend`, run `npm ci` and `npm run quality`.

Keep commits scoped to one story/component. Do not mix unrelated cleanup.

After every story:
- update contract/TDD docs;
- update `docs/project/implementation-checklist.md`;
- report exact tests/CI evidence;
- state any manual operator action still required.

## Manual dependencies to surface, not fake

Ask the repository owner only when genuinely required for:
- restricted dataset acquisition/acceptance of terms;
- cloud/database/object-storage credentials;
- deployment account access;
- GitHub repository rename/archive/ruleset administration.

Never fabricate credentials, dataset access or successful external deployment.

## Definition of “MVP done”

Do not call the MVP done until:
- one supported MP3/WAV saxophone recording can traverse Frontend → Backend → AI worker;
- the job survives asynchronous processing/restart;
- review and immutable revisions are durable;
- at least MIDI and MusicXML are produced, with SVG when renderer succeeds;
- editing a revision can regenerate its derived artifacts;
- downloads work through Backend;
- authorization/privacy/retention basics are in place;
- the three component quality gates and cross-component E2E are green.

When all of that is complete, produce a final gap report before starting source separation or multiinstrument work.
