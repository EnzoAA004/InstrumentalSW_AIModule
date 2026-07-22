# Transcription review API — v1

## Purpose

SAX-042 exposes an immutable, read-only review snapshot for a transcription job only when a real `WrittenPitchTranscriptionResult` has already been registered internally.

```text
WrittenPitchTranscriptionResult
→ TranscriptionReviewRepository
→ GetTranscriptionReview
→ GET /api/v1/transcriptions/{job_id}/review
```

The GET never runs transcription, loads audio, invokes a model, or creates synthetic events.

## Internal storage port

`TranscriptionReviewRepository` stores one exact `WrittenPitchTranscriptionResult` reference for each UUID. `InMemoryTranscriptionReviewRepository` uses an in-memory dictionary only. It performs no serialization, pickle, filesystem access, audio storage, TTL, revision generation, or mutation.

## Internal registration

`RegisterTranscriptionReview` is not exposed through HTTP. It requires an existing job, requires the result saxophone type to equal the job saxophone type, stores the exact object reference, returns that same object, and does not change job status or rerun earlier transcription, confidence, or written-pitch policies.

## Query behavior

`GetTranscriptionReview` distinguishes:

- unknown job;
- known job without a registered result;
- known job with an available result.

The produced snapshot preserves source order and exact values. Event indices are `0..N-1`; empty results are valid.

## HTTP endpoint

```http
GET /api/v1/transcriptions/{job_id}/review
Accept: application/json
```

HTTP 200 contains exactly:

```text
job_id
schema_version
note_event_schema_version
low_confidence_policy_version
written_pitch_policy_version
saxophone_type
low_confidence_threshold
confidence_interpretation
confidence_method
summary.event_count
summary.low_confidence_count
events[]
```

Each event contains:

```text
index
pitch_concert_midi
written_pitch_midi
onset_seconds
offset_seconds
velocity
confidence
is_low_confidence
```

All policy/schema versions are `1.0`. Confidence interpretation is exactly `model_signal_not_calibrated_accuracy`. Confidence remains a unit-interval model signal, not a percentage or calibrated accuracy claim.

The API does not add `duration_seconds`, note names, enharmonic spelling, key, quantization, measure information, score data, or audio data.

## Errors

```text
400 INVALID_JOB_ID
404 TRANSCRIPTION_NOT_FOUND
409 TRANSCRIPTION_RESULT_NOT_READY
```

Stable not-ready envelope:

```json
{
  "code": "TRANSCRIPTION_RESULT_NOT_READY",
  "message": "Transcription notes are not available yet.",
  "field": "job_id"
}
```

A normal SAX-040 upload has no automatic result producer in this story and can therefore remain not ready.

## Composition and tests

`create_app` creates empty job/review repositories by default and accepts injected repositories for tests. Successful API tests register real domain results through `RegisterTranscriptionReview`; the route does not return hardcoded review JSON.

No POST, PUT, PATCH, DELETE, seed, or review-registration endpoint exists.

## Exclusions

No upload processing, inference, audio retention, `BackgroundTasks`, worker, queue, persistence, new `JobStatus`, editing, regeneration, playback, SVG, PDF, download, SAX-043, or later story is implemented.
