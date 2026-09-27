# PostgreSQL review/revision persistence contract v1

SAX-076 stores transcription review, immutable revision history and regeneration requests in PostgreSQL so API and worker processes can share state across restarts.

## Tables

- `transcription_reviews` stores one source review per transcription job and keeps the model identity, transcription settings, saxophone type and low-confidence settings needed to reconstruct the review projection.
- `transcription_review_events` stores the ordered source review events with concert pitch, written pitch, timing, velocity, confidence and low-confidence flag.
- `transcription_revisions` stores immutable revision headers keyed by `(job_id, revision_number)`.
- `transcription_revision_events` stores the ordered immutable event snapshot for each revision.
- `regeneration_requests` stores one requested regeneration per `(job_id, revision_number)`.

## Invariants

- Reviews and revision zero are initialized in one database transaction.
- Duplicate registration of the same review and revision zero is idempotent.
- Registering a different review for an existing job is rejected.
- Revision numbers are sequential from zero, and non-zero revisions point to the previous revision number.
- Appending a revision uses the caller's expected latest revision as an optimistic concurrency guard.
- Revision event snapshots are immutable. Later revisions copy and change events by creating a new revision.
- Regeneration requests are idempotent per `(job_id, revision_number)`.
- Database foreign keys reject orphan reviews, revisions and regeneration requests.

## Story boundary

This contract does not execute regeneration work, choose production repositories at startup, or define retention/auth behavior. Those remain in later stories, starting with SAX-077 for production composition.
