# InstrumentalSW AI Module

Python/FastAPI module for InstrumentalSW (Saxo), developed through reproducible TDD iterations.

## Requirements

- Python `>=3.11,<3.14`
- `pip`
- FFmpeg for canonical-audio integration tests

```bash
ffmpeg -version
python -m pip install -e ".[dev]"
python -m uvicorn saxo_ai.main:app --reload
```

Unit tests do not require FFmpeg. CI installs FFmpeg and runs the protected quality matrix on Python 3.11, 3.12, and 3.13. The optional real FiloSax baseline is required only on Python 3.11.

## HTTP API

```text
GET  /health
POST /api/v1/transcriptions
GET  /api/v1/transcriptions/{job_id}
GET  /api/v1/transcriptions/{job_id}/review
GET  /api/v1/transcriptions/{job_id}/revisions
GET  /api/v1/transcriptions/{job_id}/revisions/{revision_number}
POST /api/v1/transcriptions/{job_id}/revisions
POST /api/v1/transcriptions/{job_id}/revisions/{revision_number}/regeneration-requests
GET  /api/v1/transcriptions/{job_id}/revisions/{revision_number}/artifacts
GET  /api/v1/transcriptions/{job_id}/revisions/{revision_number}/artifacts/{artifact_id}
```

Jobs, review results, revisions, regeneration requests, and registered artifact bundles are in-memory only. A job begins with `UPLOADED`; the only current statuses are `UPLOADED` and `FAILED`.

## Upload and status

`POST /api/v1/transcriptions` accepts MP3/WAV multipart fields:

```text
file
saxophone_type: soprano | alto | tenor | baritone
input_mode:     solo | mixture
```

The upload path performs bounded hashing and creates a job record. It does not run transcription or retain audio. `GET /api/v1/transcriptions/{job_id}` returns the current in-memory job state.

## Transcription review API

SAX-042 exposes an immutable note review only when a real `WrittenPitchTranscriptionResult` has already been registered through the internal application case:

```text
WrittenPitchTranscriptionResult
→ RegisterTranscriptionReview
→ TranscriptionReviewRepository
→ GetTranscriptionReview
→ GET /api/v1/transcriptions/{job_id}/review
```

The GET is read-only. It never executes inference, processes the upload, loads or stores audio, creates synthetic notes, changes job status, or starts background work.

HTTP 200 preserves:

```text
job_id
schema_version: 1.0
note_event_schema_version: 1.0
low_confidence_policy_version: 1.0
written_pitch_policy_version: 1.0
saxophone_type
low_confidence_threshold
confidence_interpretation
confidence_method
summary.event_count
summary.low_confidence_count
ordered events
```

Each source event preserves concert/written MIDI, onset, offset, velocity, confidence, and low-confidence marker. Confidence is a model signal in `0..1`, not calibrated accuracy.

A known job without a registered result returns HTTP 409 `TRANSCRIPTION_RESULT_NOT_READY`. An unknown job returns 404. A malformed UUID returns `400 INVALID_JOB_ID`. There is no public route for registering the source review.

See [`docs/contracts/transcription-review-api-v1.md`](docs/contracts/transcription-review-api-v1.md) and [`docs/tdd/iteration-017.md`](docs/tdd/iteration-017.md).

## Immutable human revisions

SAX-043 initializes the real SAX-042 review and immutable revision zero through one atomic registration boundary:

```text
WrittenPitchTranscriptionResult
→ revision 0 (original)
→ revision 1
→ revision 2
→ ...
```

`TranscriptionReviewRegistrationRepository.initialize(...)` validates the aggregate before swapping one in-memory snapshot containing both the source review and revision history. A preexisting identical review with no history is completed with exactly one revision zero. Re-registering the same object is idempotent; a different review instance is rejected. Readers sharing the store cannot observe only one half of the initialization, and job status is unchanged.

The source object and every historical revision remain unchanged. A complete new revision is appended for each explicit operation batch.

Stable IDs are:

```text
model source: source-{source_index}
human added: human-{UUID}
```

Model events preserve source index, velocity, confidence, and low-confidence status. Human events have null model confidence and use velocity 64 when omitted.

Editable values are written MIDI, onset, and offset. Concert MIDI is derived authoritatively:

```text
pitch_concert_midi = written_pitch_midi - saxophone offset
```

The API validates written and concert MIDI `0..127`, finite timing, velocity, provenance, exact fields, unique IDs, summary counts, history sequence, and instrument consistency. Update retains position, delete removes a position, add appends, no implicit sorting occurs, overlaps remain valid, and zero events are allowed.

A revision request must use the current latest revision number. A stale base returns `409 REVISION_CONFLICT` and never overwrites concurrent work.

Read endpoints expose complete immutable detail and summary history. Historical revisions cannot be updated or deleted.

See [`docs/contracts/transcription-revisions-api-v1.md`](docs/contracts/transcription-revisions-api-v1.md) and [`docs/tdd/iteration-018.md`](docs/tdd/iteration-018.md).

## Derived-artifact request boundary

A successful edit has `derived_artifacts_status = STALE`. The explicit regeneration endpoint records one idempotent request per revision:

```text
status: REQUESTED
requested_artifacts: midi, musicxml, svg
```

The read projection then reports `REGENERATION_REQUESTED`. The request creates no MIDI, MusicXML, or SVG bytes, does not call existing exporters, and does not claim completion.

Editing, validation and revision history are implemented. A regeneration request is recorded explicitly. Artifact execution remains pending.

There is no worker, queue, `BackgroundTasks`, percentage, ETA, completion state, object storage, or replacement artifact in SAX-043.

## Revision artifact downloads

SAX-045 exposes read-only list and binary download transport for already-materialized artifacts that have been registered internally for a concrete immutable revision.

Architecture:

```text
FastAPI artifact routes
→ ListRevisionArtifacts / GetRevisionArtifact
→ separate RevisionArtifactRepository
→ in-memory RevisionArtifactBundle
```

The independent repository supports:

```text
save(bundle)
get_bundle(job_id, revision_number)
get_artifact(job_id, revision_number, artifact_id)
```

`RegisterRevisionArtifacts` is internal and has no HTTP route. It verifies that the job and revision exist, preserves exact immutable bytes, is idempotent for an exact/equal bundle, and rejects an incompatible replacement.

A registered bundle is non-empty and binds every artifact to:

```text
job_id
revision_number
artifact_id
artifact_type
```

Descriptors contain:

```text
artifact_id
artifact_type
filename
media_type
extension
size_bytes
sha256
order
```

Supported public types are exactly:

```text
MIDI     audio/midi                                  .mid
MusicXML application/vnd.recordare.musicxml+xml      .musicxml
SVG      image/svg+xml                               .svg
```

Stable IDs are safe identifiers such as `midi`, `musicxml`, and `svg-page-001`; paths are not IDs. IDs and filenames are unique within the revision, order is deterministic `0..N-1`, filenames are safe relative basenames, `size_bytes` equals the exact byte length, and `sha256` is the exact lowercase 64-character digest.

The list endpoint returns descriptors without bytes or base64. The binary endpoint returns exact bytes with:

```text
Content-Type
Content-Disposition: attachment; filename="safe-name.ext"
Content-Length
X-Content-Type-Options: nosniff
Cache-Control: private, no-store
X-Content-SHA256
ETag: "sha256-{digest}"
```

Stable errors distinguish:

```text
400 INVALID_JOB_ID
404 TRANSCRIPTION_NOT_FOUND
404 REVISION_NOT_FOUND
404 ARTIFACT_NOT_FOUND
409 ARTIFACTS_NOT_READY
```

Integration tests materialize real MIDI, MusicXML, and multiple SVG pages using the existing SAX-031, SAX-034, and SAX-035 capabilities, then register the resulting bytes. Neither GET route invokes an exporter, rhythm quantizer, MusicXML encoder, Verovio renderer, transcription model, or regeneration worker.

There is no public artifact write route, database, filesystem, object storage, signed URL, ZIP, PDF, or automatic generation.

MIDI, MusicXML and SVG download transport is implemented for registered artifacts. Artifact generation from a normal uploaded job remains pending. PDF is not implemented.

See [`docs/contracts/revision-artifact-download-api-v1.md`](docs/contracts/revision-artifact-download-api-v1.md) and [`docs/tdd/iteration-019.md`](docs/tdd/iteration-019.md).

## Internal audio capabilities

The module includes bounded upload hashing, explicit size/duration limits, canonical WAV conversion through FFmpeg, stable invalid-content failures, and immutable job revisions. Canonical conversion writes only to caller-provided destinations and is not connected to the upload endpoint.

Default canonical representation:

```text
container:               wav
codec:                   pcm_s16le
sample_rate_hz:          16000
channels:                1
sample_width_bits:       16
amplitude_normalization: none
preprocessing schema:    1.0
```

Default processing limits:

```text
max_size_bytes:        104857600
max_duration_seconds:  900.0
```

## Note and notation contracts

The internal pipeline contains immutable, model-independent contracts for:

- NoteEvent schema 1.0;
- deterministic event postprocessing;
- low-confidence annotation;
- written saxophone pitch;
- concert-pitch MIDI export;
- tempo estimation and manual revision;
- monophonic rhythm quantization;
- transposing MusicXML 4.0 export;
- revision-linked SVG score rendering.

The written-pitch rule is:

```text
soprano Bb   +2
alto Eb      +9
tenor Bb    +14
baritone Eb +21
```

Concert and written MIDI remain distinct. Low-confidence events are never hidden or assigned to human-added notes.

Contracts:

- [`docs/contracts/note-event-v1.md`](docs/contracts/note-event-v1.md)
- [`docs/contracts/note-event-postprocessing-v1.md`](docs/contracts/note-event-postprocessing-v1.md)
- [`docs/contracts/note-confidence-v1.md`](docs/contracts/note-confidence-v1.md)
- [`docs/contracts/written-pitch-v1.md`](docs/contracts/written-pitch-v1.md)
- [`docs/contracts/midi-export-v1.md`](docs/contracts/midi-export-v1.md)
- [`docs/contracts/tempo-resolution-v1.md`](docs/contracts/tempo-resolution-v1.md)
- [`docs/contracts/rhythm-quantization-v1.md`](docs/contracts/rhythm-quantization-v1.md)
- [`docs/contracts/musicxml-export-v1.md`](docs/contracts/musicxml-export-v1.md)
- [`docs/contracts/score-rendering-v1.md`](docs/contracts/score-rendering-v1.md)

These internal exporters are not automatically connected to uploaded jobs or SAX-043 regeneration requests. SAX-045 registers their already-produced bytes only through an internal application use case.

## Optional FiloSax baseline

Install the controlled Python 3.11 baseline with:

```bash
python scripts/install_baseline.py
```

The installer verifies pinned source revisions and provenance. The baseline is not instantiated by the FastAPI composition root and no HTTP GET or revision POST triggers model download or inference.

See [`docs/baselines/hf-saxophone-v1.md`](docs/baselines/hf-saxophone-v1.md).

## Quality

```bash
python scripts/check_quality.py
python -m pytest
python -m pytest -m "not integration"
python -m pytest -m integration
python -m pytest -m midi_integration
python -m pytest -m musicxml_integration
python -m pytest -m score_render_integration
python -m pytest -m baseline_integration
python -m pytest --cov=saxo_ai --cov-report=term-missing --cov-report=xml
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
python -m mypy
```

The protected quality command enforces pytest coverage of at least 90%, Ruff lint, Ruff format, and strict mypy. Any failed stage stops the quality gate and returns a non-zero exit code.

## Boundaries

SAX-045 does not implement automatic upload processing, artifact generation from GET, pending regeneration execution, a worker, queue, `BackgroundTasks`, persistence, filesystem storage, object storage, signed URLs, ZIP, PDF, a new `JobStatus`, a public artifact registration endpoint, authentication, authorization, retention, playback, or SAX-050. A normal uploaded job can legitimately have no artifact bundle and return `ARTIFACTS_NOT_READY`.
