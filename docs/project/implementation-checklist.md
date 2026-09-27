# Saxo implementation checklist

Audit date: 2026-09-27

Legend:

- ✅ implemented and merged in the corresponding stable component branch;
- 🟡 implemented partially or currently in progress;
- ⬜ not implemented;
- 🧪 migrated/implemented but still requiring integration validation.

## E0 — Foundations and quality

| Story | Status | Current state |
|---|---:|---|
| SAX-000 Initialize repository | ✅ | Reproducible Python project, documentation and tests exist. Backend and Frontend also have their own reproducible build roots. |
| SAX-001 Validate input files | ✅ | MP3/WAV extension and empty input validation implemented in AI API. |
| SAX-002 Create/query job | ✅ | API exists; job persistence later moved beyond the original in-memory-only version through SAX-070. |
| SAX-003 CI and quality gates | ✅ | AI quality matrix exists. Backend and Frontend quality workflows were migrated and retargeted to their component branches. |

## E1 — Ingestion and preprocessing

| Story | Status | Current state |
|---|---:|---|
| SAX-010 SHA-256 audio hash | ✅ | Implemented and tested. |
| SAX-011 Canonical audio conversion | ✅ | FFmpeg adapter, canonical WAV PCM and integration tests exist. |
| SAX-012 Corrupt-audio detection | ✅ | Stable invalid-content failure path exists. |
| SAX-013 Size/duration limits | ✅ | Configurable limits and boundary tests exist. |
| SAX-014 Durable original-audio storage | ✅ | Added after the original backlog; accepted source audio can be stored privately for worker recovery. |

## E2 — Monophonic transcription

| Story | Status | Current state |
|---|---:|---|
| SAX-020 NoteEvent contract | ✅ | Versioned model-independent event contract implemented. |
| SAX-021 Audio→MIDI baseline | ✅ | Pinned FiloSax/HF baseline adapter and real integration coverage exist. |
| SAX-022 Event filtering/deduplication | ✅ | Deterministic post-processing exists. |
| SAX-023 Low-confidence markers | ✅ | Events retain confidence and a low-confidence flag. |
| SAX-036 End-to-end monophonic processor | ✅ | PR #29 composes canonicalization → real FiloSax baseline → post-processing → confidence → transposition → tempo → quantization → MIDI/MusicXML/SVG → revision zero. The shared generated fixture drives both baseline and processor E2E coverage, including the real Python 3.11 pinned-baseline job. Full Quality is green. |

## E3 — Transposition, notation and export

| Story | Status | Current state |
|---|---:|---|
| SAX-030 Saxophone transposition | ✅ | Soprano/alto/tenor/baritone written-pitch rules implemented. |
| SAX-031 MIDI export | ✅ | Real encoder/parser integration exists. |
| SAX-032 Tempo estimate/manual override | ✅ | Automatic estimate and manual replacement implemented. |
| SAX-033 Monophonic rhythm quantization | ✅ | Grid, rests, timing deltas and overlap policy implemented. |
| SAX-034 MusicXML | ✅ | MusicXML 4.0 export and external reader validation implemented. |
| SAX-035 Score rendering | ✅ | SVG rendering with Verovio implemented; controlled render failures preserve upstream artifacts. |

## E4 — Product and human review

| Story | Status | Current state |
|---|---:|---|
| SAX-040 Upload from frontend | ✅ | Frontend upload flow and Spring Boot upload gateway are present in migrated branches. |
| SAX-041 Job progress | ✅ | Frontend progress UI and Backend status gateway are present. |
| SAX-042 Review notes/confidence | ✅ | AI review API, Backend gateway and Frontend visualization exist. |
| SAX-043 Edit note events | ✅ | Immutable revisions, Backend revision gateway and Frontend editor exist. |
| SAX-044 Synchronized playback | ✅ | Frontend local synchronized playback exists. |
| SAX-045 Download artifacts | ✅ | AI binary/list API, Backend gateway and Frontend downloads exist. |
| Automatic execution after upload | 🟡 | Queue/worker exists, but production composition depends on finishing SAX-036 and the persistence/runtime gaps below. |
| Regeneration after an edited revision | 🟡 | Request recording exists; actual worker execution/regeneration of a requested revision is not yet wired end-to-end. |

## E5 — Data, evaluation and training

| Story | Status | Current state |
|---|---:|---|
| SAX-050 Dataset provenance/license registry | ✅ | Implemented. |
| SAX-051 Reproducible FiloSax preparation | ✅ | Scripts/manifests/checksums implemented; restricted dataset acquisition remains operator-side. |
| SAX-052 Leakage-safe splits | ✅ | Implemented. |
| SAX-053 AMT metrics | ✅ | Note transcription metrics implemented. |
| SAX-054 Compare baselines | ⬜ | No completed comparison/evaluation story yet. This remains P0. |
| SAX-055 Train/fine-tune specialized model | ⬜ | Deferred until objective baseline evaluation exists. |
| SAX-056 Internal model card | ⬜ | Deferred until a selected/trained model is ready. |

## E6 — Source separation

| Story | Status | Current state |
|---|---:|---|
| SAX-060 sax/other dataset | ⬜ | Post-MVP. |
| SAX-061 sax/other separation | ⬜ | Post-MVP. |
| SAX-062 chained pipeline evaluation | ⬜ | Post-MVP. |

## E7 — Cloud, security and operations

| Story | Status | Current state |
|---|---:|---|
| SAX-070 PostgreSQL jobs | ✅ | Real migrated job repository exists. |
| SAX-071 Private object storage | ✅ | S3-compatible private artifact/original-audio adapters exist. |
| SAX-072 Durable queue/worker | ✅ | PostgreSQL queue, lease/reclaim, retry and worker contract merged. |
| SAX-073 Authentication/authorization | ⬜ | Not implemented. |
| SAX-074 Logs/metrics/correlation | ⬜ | Not implemented as a complete operational story. |
| SAX-075 Retention/deletion | ⬜ | Not implemented. |

## E8 — Multiinstrument

| Story | Status | Current state |
|---|---:|---|
| SAX-080 Detect instruments | ⬜ | Post-MVP. |
| SAX-081 Multiple stems/engines | ⬜ | Post-MVP. |
| SAX-082 Multi-track score | ⬜ | Post-MVP. |

## Integration gaps discovered after the original backlog

These are required before calling the first product flow operational across separate API/worker processes.

### SAX-076 — Persist review/revision/regeneration state in PostgreSQL — P0/P1 boundary

Status: ✅

Current branch:
- `feature/SAX-076-postgres-review-revision-persistence` adds the PostgreSQL adapter, schema migration, integration contract tests and durability contract docs for review, immutable revisions and regeneration requests.
- Quality #462 is green for the SAX-076 hardening branch, including real PostgreSQL persistence and concurrent optimistic-writer coverage.

Required:
- PostgreSQL repositories for source review, immutable revision history and regeneration requests;
- migration schema and indexes;
- atomic initialization of review + revision zero;
- optimistic/concurrency guarantees equivalent to current in-memory behavior;
- API and worker processes must see the same state after restart.

Reason: jobs and queue are durable, but review/revision/regeneration state still relies on in-memory repositories in the current composition.

### SAX-077 — Production composition root and worker executable — P0 for runnable MVP

Status: ⬜

Required:
- explicit environment configuration for PostgreSQL, object storage and queue;
- FastAPI composition using durable adapters rather than development defaults;
- worker CLI/process composition using the same PostgreSQL/object-storage configuration;
- concrete `MonophonicTranscriptionProcessor` plugged into `TranscriptionWorker`;
- graceful startup/shutdown and non-zero exit on invalid configuration;
- no model download triggered by read-only HTTP endpoints.

### SAX-078 — Cross-component end-to-end product test — P0 for release confidence

Status: ⬜

Required:
- Frontend → Spring Boot → FastAPI upload;
- queued processing → worker → completed/failed state;
- review/revision visible from API and UI;
- edit → regeneration request → regenerated artifacts;
- MIDI/MusicXML/SVG download through Backend;
- restart API/worker during test to prove durable state;
- stable error behavior for corrupt audio;
- no secrets or private datasets in CI.

## Recommended execution order

### Finish the usable monophonic MVP first

1. SAX-077 — production API + worker composition.
2. SAX-078 — full cross-component E2E.
3. SAX-073 — authentication/authorization.
4. SAX-074 — logs, metrics and correlation.
5. SAX-075 — retention/deletion.
6. SAX-054 — objective baseline comparison on the controlled evaluation set.
7. Decide from SAX-054 whether SAX-055 fine-tuning is justified.
8. SAX-056 if a specialized/selected model is promoted.

### Only after that

10. SAX-060 → SAX-062 source separation.
11. SAX-080 → SAX-082 multiinstrument pipeline.

## Completed story: SAX-036

SAX-036 closes the first concrete monophonic audio-to-score processor story for the AI module.

Final state:
- the processor composes canonicalization, the real FiloSax baseline, post-processing, confidence marking, written-pitch transposition, tempo resolution, rhythm quantization, MIDI export, MusicXML export, SVG rendering, revision-zero review registration and revision artifact registration;
- the baseline integration and processor E2E use the shared generated fixture in `tests/synthetic_audio.py`;
- `MonophonicProcessingDiagnostics` records stage counts and artifact sizes for E2E observability without changing product behavior;
- Quality is green, including the Python 3.11 real pinned-baseline integration path.

The next P0 gap is SAX-077: production API and worker composition using the durable PostgreSQL/object-storage adapters.
