# Private object storage for revision artifacts — v1

## Objective

SAX-071 gives revision artifacts (MIDI/MusicXML/SVG bytes) durable, private
storage that survives an AI-module restart: binary content lives in an
S3-compatible object store (private MinIO in development, or real AWS S3),
metadata lives in Postgres (extending SAX-070's pattern). Together they
replace `InMemoryRevisionArtifactRepository` for anyone who opts in.

## Traceability

```text
SAX-071
→ SAX-070 (Postgres engine, migration pattern, testcontainers fixture)
→ RevisionArtifactRepository (existing Protocol, application/ports.py)
→ ObjectStorage (new Protocol, application/ports.py)
→ SAXO_OBJECT_STORAGE_* / load_object_storage_settings
→ S3ObjectStorage
→ revision_artifact_bundles / revision_artifacts (SQLAlchemy Core tables)
→ ObjectStorageRevisionArtifactRepository
→ migrations/versions/0002_create_revision_artifacts.py
→ tests/unit/test_object_storage_configuration.py
→ tests/integration/test_s3_object_storage.py (real MinIO via testcontainers)
→ tests/integration/test_object_storage_revision_artifact_repository.py (real MinIO + Postgres)
```

## Why bytes and metadata live in different systems

Bytes never touch Postgres — `revision_artifacts.storage_key` records where
the content lives, not the content itself. This keeps rows small and avoids
mixing a binary blob store's access patterns with a relational one.
`ObjectStorageRevisionArtifactRepository.save` writes objects to storage
*before* inserting metadata rows: if the metadata insert fails, an orphan
object can be left in storage, but a metadata row can never point at bytes
that don't exist. The reverse order would risk exactly that — a promise the
API answers for that storage can't keep. There is no distributed
transaction/outbox pattern here; orphan-object cleanup is out of scope.

## Configuration

```text
SAXO_OBJECT_STORAGE_ENDPOINT_URL   e.g. http://minio.internal:9000  (required)
SAXO_OBJECT_STORAGE_BUCKET         e.g. saxo-artifacts              (required)
SAXO_OBJECT_STORAGE_ACCESS_KEY                                     (required)
SAXO_OBJECT_STORAGE_SECRET_KEY                                     (required)
SAXO_OBJECT_STORAGE_REGION         defaults to us-east-1
```

`load_object_storage_settings` raises `ObjectStorageConfigurationError` if
any required variable is unset or blank — no default bucket or credentials.
Bucket creation is an operational/deployment concern, not something this
code does; tests create their own throwaway bucket against a throwaway
MinIO container.

## Signed URLs

`ObjectStorage.generate_presigned_get_url(key, expires_in_seconds=...)`
produces a time-limited, storage-signed URL. This project's download flow
(SAX-045) intentionally never exposes a public storage URL to the browser —
downloads still go through the FastAPI artifact endpoint, which is proxied
by the Backend gateway. The presigned-URL capability exists for
internal/server-side use (e.g. handing a short-lived URL to a worker) and is
exercised end-to-end in tests; nothing in this story wires it into the
public HTTP download response.

## Repository behavior

`ObjectStorageRevisionArtifactRepository.save` matches
`InMemoryRevisionArtifactRepository`'s existing semantics: saving an
identical bundle for an already-registered `(job_id, revision_number)` is a
no-op returning the existing bundle; saving a *different* bundle for the
same key raises `RevisionArtifactConflictError`. Equality-checking requires
re-fetching the existing bundle's bytes from storage — acceptable given
artifact sizes (MIDI/MusicXML/SVG are KB-scale, not audio).

## Testing

Both new integration test files are marked `object_storage_integration`
(and the combined repository test also `postgres_integration`) and start
real, ephemeral containers: `minio/minio:latest` via a generic
`DockerContainer` (no dedicated testcontainers MinIO module ships without
pulling in an extra `minio` client dependency we don't otherwise need), and
`postgres:16-alpine` via `testcontainers.community.postgres` — reusing the
shared `postgres_engine` fixture now centralized in
`tests/integration/conftest.py`.

**Preventive fix bundled here**: `testcontainers` 4.15 deprecated
`testcontainers.postgres` in favor of `testcontainers.community.postgres`,
and this project's `filterwarnings = ["error"]` turns that deprecation
warning into a collection-time error. Since dependencies aren't pinned to
exact versions, the already-merged SAX-070 test would have broken on its
next fresh `pip install` (CI has no lockfile). Fixed here alongside
centralizing the fixture, rather than leaving a latent, version-triggered
break for a future PR to rediscover.

## Architecture

```text
domain
  RevisionArtifact / RevisionArtifactBundle / RevisionArtifactDescriptor
  (existing, unchanged) — still hold real bytes in memory once loaded;
  storage is purely how they get in and out of the process.

application
  ObjectStorage (new Protocol) — put/get/presigned URL, no public-URL leak.

infrastructure
  object_storage_configuration.py            — env-var loading, no defaults.
  s3_object_storage.py                        — boto3-backed adapter, works
                                                 against MinIO or AWS S3.
  postgres_schema.py                          — extended with
                                                 revision_artifact_bundles /
                                                 revision_artifacts.
  object_storage_revision_artifact_repository.py — Protocol-conformant
                                                 adapter pairing both.

migrations/versions/0002_*  — Alembic, targets the extended metadata.
```

## Still deferred

- `TranscriptionReviewRepository`, `TranscriptionRevisionRepository`,
  `RegenerationRequestRepository` remain in-memory (unchanged from SAX-070's
  documented gap) — a revision's artifacts can now outlive a restart, but
  the revision record pointing at them still cannot.
- Orphan-object cleanup / reconciliation between storage and Postgres after
  a partial failure.
- Wiring a presigned URL into any HTTP response; today it's a repository
  capability, not a product feature.
