# Transcription review gateway — v1

## Purpose

SAX-042 adds the Spring Boot read gateway between the browser and the existing FastAPI review endpoint.

```text
Next.js GET /api/v1/transcriptions/{job_id}/review
→ Spring Boot
→ FastAPI GET /api/v1/transcriptions/{job_id}/review
```

FastAPI remains authoritative. Spring neither persists nor reconstructs review data.

## Architecture

```text
TranscriptionReviewController
→ GetTranscriptionReview
→ TranscriptionReviewGateway
→ FastApiTranscriptionReviewClient
```

The review port is independent from the existing upload/status gateway.

## Public endpoint

```http
GET /api/v1/transcriptions/{job_id}/review
Accept: application/json
```

HTTP 200 preserves the complete review snapshot: job identity, all schema/policy versions, saxophone type, threshold, confidence interpretation/method, summary counts, exact event order, concert/written MIDI, onset, offset, velocity, confidence, and low-confidence marker.

Spring adds no duration, note name, spelling, key, quantization, score, or audio field.

## Validation

The client accepts only HTTP 200 and validates:

- requested/returned UUID equality;
- all four versions exactly `1.0`;
- known saxophone type;
- finite threshold in `0..1`;
- exact interpretation `model_signal_not_calibrated_accuracy`;
- nonblank confidence method;
- nonnegative summary counts;
- array event shape;
- consecutive indices `0..N-1`;
- concert/written MIDI and velocity in `0..127`;
- finite, nonnegative onset;
- finite offset strictly greater than onset;
- finite confidence in `0..1`;
- real boolean low-confidence marker;
- event and low-confidence count consistency.

An incompatible HTTP 200 becomes a controlled 502 and its body is never exposed.

## Error mapping

```text
malformed route UUID → 400 INVALID_JOB_ID
FastAPI 404          → 404 TRANSCRIPTION_NOT_FOUND
FastAPI 409          → 409 TRANSCRIPTION_RESULT_NOT_READY
FastAPI 422          → 400 INVALID_JOB_ID
FastAPI 5xx/other    → 502 AI_SERVICE_ERROR
timeout/refusal      → 502 AI_SERVICE_UNAVAILABLE
invalid HTTP 200     → 502 AI_SERVICE_ERROR
```

Not-ready envelope:

```json
{
  "code": "TRANSCRIPTION_RESULT_NOT_READY",
  "message": "Transcription notes are not available yet.",
  "field": "job_id"
}
```

No upstream HTML, URL, hostname, stack trace, or internal payload is returned publicly.

## Transport and storage

The internal request is a bodyless GET with the exact UUID and path. It is not multipart. The response is request-scoped and is not stored in a repository, database, cache, file, or object store.

## Tests

A real JDK HTTP server verifies method, path, body absence, full response parsing, 404, 409, 422, 5xx, timeout, refusal, malformed JSON, UUID mismatch, unknown versions, bad indices/counts/events, and leakage prevention. MVC tests verify public 200/400/409 envelopes.

## Exclusions

No inference, upload processing, audio storage, BackgroundTasks, worker, queue, new status, review polling, synthetic notes, editing, playback, download, SVG/PDF, SAX-043, or later story is included.
