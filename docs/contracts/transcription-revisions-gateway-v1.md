# Transcription revisions gateway — v1

## Objective

SAX-043 adds the Spring Boot product gateway for immutable transcription revisions. The browser calls Spring; Spring forwards the request to the existing FastAPI AI service and validates the complete response.

```text
Next.js
→ Spring Boot product API
→ FastAPI AI service
```

FastAPI remains authoritative. Spring does not store, reconstruct, edit, sort, or regenerate revisions.

## Public endpoints

```http
GET  /api/v1/transcriptions/{job_id}/revisions
GET  /api/v1/transcriptions/{job_id}/revisions/{revision_number}
POST /api/v1/transcriptions/{job_id}/revisions
POST /api/v1/transcriptions/{job_id}/revisions/{revision_number}/regeneration-requests
```

Each request is forwarded once to the identical FastAPI path. GET requests and regeneration requests are bodyless. Revision creation forwards exact JSON with `Content-Type: application/json`.

## Architecture

```text
TranscriptionRevisionController
→ GetTranscriptionRevisionHistory
→ GetTranscriptionRevision
→ CreateTranscriptionRevision
→ RequestTranscriptionRegeneration
→ TranscriptionRevisionGateway
→ FastApiTranscriptionRevisionClient
```

The revision gateway is independent from upload, status, and SAX-042 read-review gateways.

## Revision creation body

```json
{
  "base_revision_number": 0,
  "operations": [
    {
      "type": "update",
      "event_id": "source-0",
      "written_pitch_midi": 70,
      "onset_seconds": 0.1,
      "offset_seconds": 0.6
    },
    {
      "type": "add",
      "written_pitch_midi": 72,
      "onset_seconds": 0.7,
      "offset_seconds": 1.0,
      "velocity": 64
    },
    {
      "type": "delete",
      "event_id": "source-1"
    }
  ]
}
```

Spring validates the envelope and exact operation fields before forwarding. Unknown fields, empty operation arrays, unsupported types, duplicate update/delete targets, invalid numeric shapes, and malformed route identifiers become controlled public errors. FastAPI validates the musical and historical rules again.

## Complete response validation

Spring accepts only the expected success status and validates every response field.

History validation includes:

- requested/returned UUID identity;
- non-empty sequential revisions `0..N-1`;
- latest/count consistency;
- parent chain;
- parseable timestamps;
- non-negative model/human/total counts;
- count consistency;
- derived-artifact state.

Revision-detail validation includes:

- requested job and revision identity;
- schema version `1.0`;
- known saxophone type;
- unique stable event IDs;
- model `source-{index}` and human `human-{UUID}` identity;
- concert/written MIDI and velocity `0..127`;
- finite non-negative onset and offset greater than onset;
- model confidence `0..1` and Boolean marker;
- null confidence/source index for human events;
- summary/event consistency;
- valid derived-artifact state.

Regeneration-response validation includes:

```text
request UUID
job UUID identity
revision identity
status = REQUESTED
requested_artifacts = midi, musicxml, svg
```

Unexpected fields, malformed JSON, identity mismatches, invalid counts, or unsupported values become `502 AI_SERVICE_ERROR`. Raw upstream bodies, HTML, URLs, stack traces, and internal details are not exposed.

## Error mapping

```text
FastAPI 400 INVALID_JOB_ID              → 400
FastAPI 404 TRANSCRIPTION_NOT_FOUND      → 404
FastAPI 404 REVISION_NOT_FOUND           → 404
FastAPI 409 TRANSCRIPTION_RESULT_NOT_READY → 409
FastAPI 409 REVISION_CONFLICT            → 409
FastAPI 422 INVALID_REVISION_OPERATION   → 422
FastAPI 422 INVALID_REVISION_EVENT       → 422
FastAPI 5xx or unexpected response       → 502 AI_SERVICE_ERROR
timeout or refusal                       → 502 AI_SERVICE_UNAVAILABLE
```

Malformed public route UUIDs are rejected before the gateway call. Invalid revision path values map to `REVISION_NOT_FOUND`.

The optimistic conflict envelope remains:

```json
{
  "code": "REVISION_CONFLICT",
  "message": "The transcription revision has changed.",
  "field": "base_revision_number"
}
```

## Regeneration boundary

Spring forwards the explicit request and returns `202 Accepted` only after validating FastAPI's `REQUESTED` response. It does not call MIDI, MusicXML, or SVG exporters and does not expose bytes, completion, percentage, or ETA.

Editing, validation and revision history are implemented across the product path.

A regeneration request is recorded explicitly by the AI service.

Artifact execution remains pending.

## Persistence and CORS

Spring has no revision repository, database, cache, filesystem record, or object storage. Every operation reaches FastAPI once.

The existing transcription CORS policy permits browser GET, POST, and OPTIONS only from `SAXO_FRONTEND_ORIGIN`, without credentials or wildcard origin.

## Out of scope

No worker, queue, `BackgroundTasks`, retries, autosave, WebSocket, SSE, artifact generation, download, authentication, SAX-044, or later story is included.
