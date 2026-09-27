# TDD iteration 021 — Durable processing queue and worker

## Story boundary

SAX-072 introduces durable asynchronous ownership and worker execution by `job_id`.

It does not change model inference or implement the final audio-to-score processor.

## Exact base

```text
32aa7940fbfc474f34f0aea2ab0e4f9a00c5276c
feature/SAX-072-durable-queue-worker
```

## RED

The first commit contained tests only:

```text
9c86d82 test(SAX-072): define durable queue and worker behavior
```

The expected RED was missing production contracts/modules: `ProcessingQueueMessage`, `TranscriptionWorker`, queue ports and asynchronous job states.

## GREEN

Production implementation adds:

- `QUEUED`, `PROCESSING` and `COMPLETED` job states;
- `SOURCE_AUDIO_MISSING` and `PROCESSING_FAILED` failure codes;
- `TranscriptionProcessingQueue` and `TranscriptionJobProcessor` ports;
- PostgreSQL queue migration `0003`;
- idempotent enqueue;
- `FOR UPDATE SKIP LOCKED` claim;
- lease expiry and reclaim;
- incrementing attempt ownership tokens;
- bounded worker retry;
- optional upload-to-queue composition;
- real PostgreSQL integration tests.

## First GREEN feedback

The first complete Quality run reached:

- 1203 tests passed, 1 skipped;
- total statement/branch coverage above the required 90%;
- Ruff lint passed;
- Ruff format passed.

Strict mypy then found one unused `type: ignore` in the new unit fake. The fake was corrected with the real `BinaryStream` and `TranscriptionJob` protocol/domain types.

## REFACTOR / concurrency hardening

Review of lease expiry exposed an ownership race: a worker whose lease had expired must not be able to acknowledge or retry a row after another worker has reclaimed it.

The queue therefore returns success/failure from `ack` and `retry`, conditional on the exact `job_id + attempt_count`. The worker changes the corresponding job state only when it still owns that attempt.

Upload ordering was also changed so the job is persisted as `QUEUED` before the queue row is made claimable, preventing a fast worker from observing an `UPLOADED` job.

## Honest status

After this story, Saxo has durable job metadata, durable source audio, durable queue ownership and a generic worker.

The worker still needs the concrete `TranscriptionJobProcessor` that chains the existing musical pipeline. That is the next MVP-critical integration step.
