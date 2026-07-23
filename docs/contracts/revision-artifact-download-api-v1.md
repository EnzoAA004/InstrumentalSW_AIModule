# Revision artifact download API — v1

## Scope and traceability

```text
SAX-045
→ existing MIDI/MusicXML/SVG exporters
→ RegisterRevisionArtifacts
→ RevisionArtifactRepository
→ list and binary GET transport
```

This contract transports already-materialized artifacts. It does not create them from an uploaded job and does not execute the pending SAX-043 regeneration request.

Supported public types are exactly `midi`, `musicxml`, and `svg`. PDF, ZIP and bulk download are absent.

## Architecture

```text
FastAPI artifact routes
→ ListRevisionArtifacts / GetRevisionArtifact
→ separate RevisionArtifactRepository
→ in-memory RevisionArtifactBundle
```

Review, revision and regeneration repositories remain independent. No database, filesystem, object storage, public URL or signed URL is introduced.

## Immutable contracts

`RevisionArtifactDescriptor` contains:

```text
artifact_id
artifact_type
filename
media_type
extension
size_bytes
sha256
order
```

`RevisionArtifact` keeps exact immutable `bytes` plus its validated descriptor. `RevisionArtifactBundle` binds artifacts to `job_id` and a non-negative `revision_number`.

A registered bundle is non-empty. IDs and filenames are unique. Orders are deterministic `0..N-1`. Replacement is idempotent only for the exact/equal bundle; incompatible replacement raises a conflict.

Stable IDs are safe identifiers such as `midi`, `musicxml`, `svg-page-001`. Paths are not IDs.

## Type metadata

```text
midi     → audio/midi                                  → .mid
musicxml → application/vnd.recordare.musicxml+xml      → .musicxml
svg      → image/svg+xml                               → .svg
```

Filenames are safe relative basenames. They contain no slash, backslash, `..`, CR/LF, hidden leading dot or incompatible extension.

`size_bytes` equals the exact byte length. `sha256` is the exact lowercase 64-character SHA-256 digest.

## Internal registration

`RegisterRevisionArtifacts` is an internal application use case. It receives a complete already-materialized bundle, verifies that the job and revision exist and stores it through the independent repository.

There is no public artifact POST, PUT, PATCH, DELETE or seed route.

Integration tests materialize real MIDI, MusicXML and multiple SVG pages using the existing SAX-031, SAX-034 and SAX-035 capabilities, then register the resulting bytes. GET routes never invoke those exporters.

## Endpoints

```http
GET /api/v1/transcriptions/{job_id}/revisions/{revision_number}/artifacts
GET /api/v1/transcriptions/{job_id}/revisions/{revision_number}/artifacts/{artifact_id}
```

The list returns descriptors only—never bytes or base64.

A successful binary response preserves exact bytes and sends:

```text
Content-Type
Content-Disposition: attachment; filename="safe-name.ext"
Content-Length
X-Content-Type-Options: nosniff
Cache-Control: private, no-store
X-Content-SHA256
ETag: "sha256-{digest}"
```

There is no redirect to storage.

## Stable errors

```text
400 INVALID_JOB_ID
404 TRANSCRIPTION_NOT_FOUND
404 REVISION_NOT_FOUND
404 ARTIFACT_NOT_FOUND
409 ARTIFACTS_NOT_READY
```

The API distinguishes unknown job, unknown revision, existing revision without bundle and missing artifact ID. It exposes no internal path, stack trace, exception, source bytes or exporter detail.

## Security and privacy

Artifact IDs and filenames are validated before headers are constructed. Bytes remain process-local and request-scoped. List responses contain no binary material. Download responses are private and non-cacheable.

## Quality and limitations

Tests cover bundle validation, idempotency/conflict, metadata-only listing, exact binary download, safe headers, stable errors, absence of write routes, absence of exporter calls during GET and real exporter registration.

MIDI, MusicXML and SVG download transport is implemented for registered artifacts. Artifact generation from a normal uploaded job remains pending. PDF is not implemented.
