# Private original-audio storage — v1

## Objective

SAX-014 persists the exact accepted MP3/WAV upload in private object storage so a later
asynchronous worker can process a transcription by `job_id` after the HTTP request ends.

This is the missing durability prerequisite discovered before SAX-072. A queue containing only
a job identifier is not useful if the request stream is the only copy of the source audio.

## Traceability

```text
SAX-014
→ CreateTranscriptionJob
→ OriginalAudioRepository
→ ObjectStorage.put_stream
→ ObjectStorageOriginalAudioRepository
→ S3ObjectStorage / MinIO or AWS S3
→ SAX-072 queue + worker
```

## Storage key

The object key is deterministic and contains no user-supplied path:

```text
original-audio/{job_id}
```

The original filename remains metadata on `TranscriptionJob`; it is not interpolated into the
storage key, so filenames cannot create object-path traversal semantics.

## Streaming

The upload is hashed first under the existing size limit. When original-audio persistence is
configured, `CreateTranscriptionJob` requires a rewindable stream, seeks it back to byte zero,
then delegates the stream to `OriginalAudioRepository.save`.

`S3ObjectStorage.put_stream` sends the readable stream directly to the S3-compatible client.
The application does not require a second full in-memory copy of an upload that may approach the
configured size limit.

## Failure ordering

Object storage is written before the job repository is updated. If private storage fails, the job
is not registered as a durable transcription that a worker could later claim without input.

As with SAX-071, there is no distributed transaction between object storage and PostgreSQL. An
unexpected database failure after object storage succeeds can leave an orphan source object;
reconciliation and retention cleanup remain SAX-075 concerns.

## Composition

The default `create_app()` behavior remains backward compatible and in-memory. Original-audio
persistence is opt-in:

```python
storage = S3ObjectStorage(load_object_storage_settings())
originals = ObjectStorageOriginalAudioRepository(storage)
app = create_app(
    job_repository=PostgresTranscriptionJobRepository(engine),
    original_audio_repository=originals,
)
```

No public object-storage URL is returned by the API.

## Still deferred

- SAX-072 durable queue and worker;
- execution of canonicalization/transcription/export in that worker;
- automatic deletion/retention of original audio (SAX-075);
- end-to-end persistence of reviews and revisions, which are still in-memory unless separately
  implemented.
