# Immutable transcription revisions API — v1

## Objective

SAX-043 provides a human-review baseline over an already produced SAX-042 `WrittenPitchTranscriptionResult`. It creates complete immutable revisions, validates edit operations authoritatively, exposes revision history, and records an explicit request for derived-artifact regeneration.

It does not run transcription from HTTP and does not regenerate MIDI, MusicXML, or SVG.

## Source and revision zero

The source object remains immutable:

```text
WrittenPitchTranscriptionResult
→ SAX-042 review source
→ revision 0
→ revision 1
→ revision 2
→ ...
```

`RegisterTranscriptionReview` builds revision zero and delegates one logical write to `TranscriptionReviewRegistrationRepository.initialize(...)`. The in-memory implementation validates the complete aggregate before replacing one shared snapshot containing both the review and its revision history. Therefore readers cannot observe a review without revision zero or revision zero without its review.

A preexisting identical review with an empty history is completed by creating exactly one revision zero. Re-registering the same result instance is idempotent and returns that exact object. A different review instance for the same job is rejected with a controlled mismatch error. Validation or simulated repository failure leaves both stores unchanged, and registration never changes `JobStatus`.

Revision zero:

- has `revision_number = 0`;
- has no parent;
- preserves the exact source order and musical values;
- uses stable IDs `source-0`, `source-1`, ...;
- marks every event as `origin = model`;
- preserves source index, velocity, confidence, and low-confidence marker;
- has `derived_artifacts_status = CURRENT`;
- does not mutate the source result or job status.

## Immutable contracts

```text
TranscriptionRevisionEvent
TranscriptionRevisionSummary
TranscriptionRevision
TranscriptionRevisionHistoryEntry
TranscriptionRevisionHistory
RegenerationRequest
```

A revision contains:

```text
job_id
schema_version = 1.0
revision_number
parent_revision_number
created_at
saxophone_type
events
summary
derived_artifacts_status
```

Allowed derived-artifact states are:

```text
CURRENT
STALE
REGENERATION_REQUESTED
```

These states belong to a revision projection and never extend `JobStatus`.

## Stable event identity

Model events use:

```text
source-{source_index}
```

Human events use:

```text
human-{UUID}
```

The UUID factory is injected for deterministic tests. IDs remain stable between revisions. Update retains the existing ID, delete removes the event only from the new revision, and add creates a previously unused human ID. Deleted IDs are never reused.

Visual or array positions are not identifiers.

## Event provenance

Each revision event contains:

```text
event_id
origin: model | human
source_index: integer | null
pitch_concert_midi
written_pitch_midi
onset_seconds
offset_seconds
velocity
confidence: number | null
is_low_confidence: boolean | null
```

Model events preserve velocity, confidence, low-confidence status, and source index. Human events use:

```text
origin = human
source_index = null
confidence = null
is_low_confidence = null
```

A human event never receives invented model confidence. New-event velocity defaults to 64 when omitted.

## Editable pitch

The client supplies only `written_pitch_midi`. The AI service derives concert pitch:

```text
pitch_concert_midi = written_pitch_midi - saxophone written-pitch offset
```

Offsets remain the existing SAX-030 values:

```text
soprano Bb   2
alto Eb      9
tenor Bb     14
baritone Eb 21
```

Both written and derived concert MIDI must be integers in `0..127`. The client cannot submit an independent concert pitch.

## Operations

```http
POST /api/v1/transcriptions/{job_id}/revisions
Content-Type: application/json
```

Example:

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

Rules:

- at least one operation is required;
- operations run in request order;
- update supplies all three editable fields;
- add supplies written pitch, onset, offset, and optional velocity;
- delete supplies only event ID;
- unknown fields are rejected;
- one event cannot be updated or deleted twice in one request;
- an unknown or already deleted ID is rejected;
- update retains position;
- delete removes that position;
- add appends;
- no implicit time sorting occurs;
- overlaps and empty results are valid;
- the operation batch is atomic.

A successful edit creates a complete new revision with `STALE`. Existing revisions are never modified or removed.

## Optimistic concurrency

A new revision may be based only on the current latest revision. When:

```text
base_revision_number != latest_revision_number
```

the API returns:

```http
409 Conflict
```

```json
{
  "code": "REVISION_CONFLICT",
  "message": "The transcription revision has changed.",
  "field": "base_revision_number"
}
```

No silent overwrite occurs.

## History endpoints

```http
GET /api/v1/transcriptions/{job_id}/revisions
GET /api/v1/transcriptions/{job_id}/revisions/{revision_number}
```

History returns:

```text
job_id
latest_revision_number
revision_count
revisions[]
```

Each history entry contains revision/parent numbers, timestamp, model/human/total event counts, and derived-artifact status. Detail returns every event in stored array order.

There is no endpoint to update or delete a historical revision.

## Authoritative validation

The AI service validates:

- UUID and known job;
- registered SAX-042 result and initialized history;
- non-negative sequential revision numbers;
- latest-revision base;
- operation type and exact allowed fields;
- non-empty stable event ID;
- unique event IDs;
- written and derived concert MIDI in `0..127`;
- finite onset `>= 0`;
- finite offset `> onset`;
- velocity in `0..127`;
- model/human provenance consistency;
- confidence in `0..1` only for model events;
- summary counts;
- saxophone consistency;
- atomic append.

Stable public errors are:

```text
INVALID_JOB_ID
TRANSCRIPTION_NOT_FOUND
TRANSCRIPTION_RESULT_NOT_READY
REVISION_NOT_FOUND
REVISION_CONFLICT
INVALID_REVISION_OPERATION
INVALID_REVISION_EVENT
```

## Explicit regeneration request

```http
POST /api/v1/transcriptions/{job_id}/revisions/{revision_number}/regeneration-requests
```

Success is `202 Accepted`:

```json
{
  "request_id": "UUID",
  "job_id": "UUID",
  "revision_number": 1,
  "status": "REQUESTED",
  "requested_artifacts": ["midi", "musicxml", "svg"]
}
```

The request repository permits one active request per revision. Repeating the endpoint returns the exact existing request. The read projection reports `REGENERATION_REQUESTED`; the immutable stored revision remains unchanged.

No MIDI, MusicXML, or SVG bytes are created. No exporter is called. No worker, queue, `BackgroundTasks`, completion state, percentage, ETA, or replacement artifact exists in SAX-043.

## Storage

Initial ports are implemented only by:

```text
InMemoryTranscriptionRevisionRepository
InMemoryRegenerationRequestRepository
```

There is no filesystem, pickle, PostgreSQL, object storage, Redis, or external cache. Restarting the AI process loses jobs, reviews, revisions, and requests.

## Scope statement

Editing, validation and revision history are implemented.

A regeneration request is recorded explicitly.

Artifact execution remains pending.
