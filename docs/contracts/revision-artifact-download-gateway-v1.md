# Revision artifact download gateway — v1

## Scope

Spring Boot exposes the product API for listing and downloading already-materialized revision artifacts while FastAPI remains authoritative.

```text
Frontend
→ TranscriptionArtifactController
→ GetRevisionArtifacts / DownloadRevisionArtifact
→ TranscriptionArtifactGateway
→ FastApiTranscriptionArtifactClient
→ FastAPI artifact API
```

Supported artifact types are MIDI, MusicXML and SVG. PDF is absent. No GET invokes export, quantization, Verovio, transcription or regeneration.

## Public routes

```http
GET /api/v1/transcriptions/{job_id}/revisions/{revision_number}/artifacts
GET /api/v1/transcriptions/{job_id}/revisions/{revision_number}/artifacts/{artifact_id}
```

Both are bodyless GET requests. The gateway is separate from upload, status, review and revision gateways.

## Descriptor validation

Every list response is validated completely:

```text
job_id
revision_number
artifact_id
artifact_type
filename
media_type
extension
size_bytes
sha256
order
```

The client requires exact response fields, returned/requested identity, safe unique IDs and filenames, deterministic order, lowercase SHA-256, positive size and compatible type/media/extension metadata.

```text
midi     / audio/midi                             / .mid
musicxml / application/vnd.recordare.musicxml+xml / .musicxml
svg      / image/svg+xml                          / .svg
```

No PDF descriptor is accepted.

## Binary validation

Before downloading bytes, Spring obtains the authoritative descriptor list. The binary response is then checked against that descriptor:

- HTTP status 200;
- exact Content-Type;
- safe exact Content-Disposition filename;
- Content-Length when present;
- X-Content-SHA256;
- actual byte length;
- locally calculated SHA-256.

`byte[]` is request-scoped for this baseline. Spring does not persist, cache, write temporary files, transform text, decode content or compress bytes.

The public response preserves:

```text
Content-Type
Content-Disposition
Content-Length
Cache-Control: private, no-store
X-Content-Type-Options: nosniff
X-Content-SHA256
ETag
```

## Errors

```text
400 INVALID_JOB_ID
404 TRANSCRIPTION_NOT_FOUND
404 REVISION_NOT_FOUND
404 ARTIFACT_NOT_FOUND
409 ARTIFACTS_NOT_READY
502 AI_SERVICE_ERROR
502 AI_SERVICE_UNAVAILABLE
```

Timeout and refused connection map to unavailable. Malformed metadata, unsafe filenames, incompatible headers, wrong size or wrong digest map to a controlled service error. Raw upstream bodies, hostnames and internal exceptions are never returned.

## Persistence and security

There is no Spring repository, database, cache, filesystem, object storage, public storage URL or signed URL. Artifact bytes are forwarded only after complete validation.

## Limitations

MIDI, MusicXML and SVG download transport is implemented for registered artifacts. Artifact generation from a normal uploaded job remains pending. PDF is not implemented. The pending SAX-043 regeneration request is not executed.
