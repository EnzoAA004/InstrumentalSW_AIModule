# PostgreSQL processing queue — v1

## Objective

SAX-072 provides the durable asynchronous execution primitive for transcription jobs after the upload HTTP request ends.

The upload path already persists the accepted original bytes in private object storage (SAX-014). This story adds a queue that stores only the server-generated `job_id`, plus claim/attempt metadata, and a worker that reloads the source audio through `OriginalAudioRepository`.

## Lifecycle

```text
UPLOADED
   ↓
QUEUED
   ↓
PROCESSING ───────────────→ COMPLETED
   │
   ├─ retryable failure ─→ QUEUED
   │
   └─ terminal failure ──→ FAILED
```

Configured uploads are persisted as `QUEUED` before the queue row becomes claimable. The default development application remains backward compatible: when no processing queue is supplied, jobs remain `UPLOADED`.

## Queue record

The PostgreSQL queue stores:

- `job_id` as the primary key and foreign key to `transcription_jobs`;
- `attempt_count`;
- `available_at`;
- `claimed_at`;
- `created_at`.

Enqueue is idempotent for the same `job_id`.

## Claiming and concurrency

Claims use `SELECT ... FOR UPDATE SKIP LOCKED` so multiple workers do not claim the same live row concurrently.

Each successful claim increments `attempt_count`; that value becomes the claim ownership token returned as `ProcessingQueueMessage.attempt`.

A claim is considered abandoned after the configured lease interval. An expired row may be claimed again with a higher attempt token.

Acknowledgement and retry operations match both `job_id` and `attempt_count`. A stale worker holding an older attempt therefore cannot delete or release the row after a newer worker has reclaimed it.

## Retry behavior

The application worker owns the maximum-attempt policy.

For a retryable processing error:

1. the worker requests queue retry;
2. only the current claim owner can release the row;
3. the job returns to `QUEUED`;
4. the queue makes it claimable after the configured retry delay.

At the maximum attempt count, the current owner acknowledges the queue row and the job becomes `FAILED` with `PROCESSING_FAILED`.

A missing original-audio object is terminal and uses `SOURCE_AUDIO_MISSING`.

## Persistence ordering and limitation

The queue row and job metadata are durable in PostgreSQL, but the generic application ports keep queue ownership operations and `TranscriptionJobRepository.save` as separate calls.

The worker first performs the attempt-guarded queue operation and only then changes the terminal/retry job state. This prevents stale claims from overwriting newer ownership, but a process/database failure between those two calls can still require reconciliation.

That tradeoff is accepted for the MVP. A later operational hardening pass can introduce a PostgreSQL unit-of-work/outbox boundary without changing the worker or processor concepts.

## Processor boundary

`TranscriptionWorker` depends on `TranscriptionJobProcessor`:

```python
processor.process(job, source_bytes)
```

SAX-072 deliberately does not implement the musical processing pipeline behind that port. The next story will compose the already existing canonicalization, baseline transcription, post-processing, confidence, transposition, tempo, quantization, MIDI, MusicXML, SVG and review-registration components.

## Deferred

- complete audio-to-score processor composition;
- long-running worker process/CLI lifecycle;
- authentication/authorization;
- centralized logs and metrics;
- retention/reconciliation cleanup;
- multi-node operational tuning.
