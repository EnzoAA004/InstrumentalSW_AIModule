# TDD iteration 020 — Durable original audio

## Story boundary

SAX-014 persists the accepted original MP3/WAV bytes in private object storage so asynchronous
processing can continue after the upload request ends.

It does not introduce a queue, worker, automatic transcription execution, retention cleanup or a
public audio-download endpoint.

## Exact base

```text
e636df43388c5d68a57fc48608b7ddbeec0d8123
feature/SAX-014-original-audio-storage
```

## RED

The first commit is tests only:

```text
146d08f test(SAX-014): define durable original-audio storage contract
```

The test imports a repository that does not yet exist and requires `CreateTranscriptionJob` to
accept an original-audio repository. The expected RED is therefore a missing production contract,
not an artificial assertion or dependency failure.

## GREEN

Minimal production adds:

- `OriginalAudioRepository` application port;
- a runtime-checkable rewindable binary stream contract;
- `ObjectStorage.put_stream`;
- streaming S3-compatible writes;
- deterministic `original-audio/{job_id}` keys;
- `ObjectStorageOriginalAudioRepository`;
- opt-in persistence in `CreateTranscriptionJob`;
- opt-in `create_app(original_audio_repository=...)` composition;
- a real MinIO streaming integration assertion.

The source object is written before the job repository is saved so a durable job is not registered
without durable worker input.

## REFACTOR / documentation

The storage key deliberately excludes the user filename. The filename remains job metadata while
the private object path depends only on the server-generated UUID.

No public URL or browser route was added. The existing SAX-071 configuration is reused.

## CI infrastructure repair

The first full GREEN run exposed a latent SAX-071 fixture failure rather than a product-code
regression: Docker Hub no longer served `minio/minio:latest`, so all S3-compatible integration
tests failed before MinIO could start. The fixture now pins the official Quay release
`quay.io/minio/minio:RELEASE.2025-07-23T15-54-02Z` instead of a mutable `latest` tag.

## Traceability

```text
SAX-014
→ upload accepted and hashed
→ stream rewound
→ OriginalAudioRepository
→ ObjectStorage.put_stream
→ original-audio/{job_id}
→ future SAX-072 worker input
```

## Honest status

Once merged, source-audio durability is available when external object storage is explicitly
composed. The default development app remains in-memory and does not persist original audio.
Queueing and worker execution remain SAX-072.
