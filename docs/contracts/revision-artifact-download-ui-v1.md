# Revision artifact download UI — v1

## Scope

The browser lists and downloads already-materialized MIDI, MusicXML and SVG revision artifacts through the Spring Boot product API.

```text
RevisionArtifactDownloads
→ getRevisionArtifacts / downloadRevisionArtifact
→ Spring Boot
→ FastAPI
```

The browser never calls FastAPI or a public storage URL directly. PDF, ZIP, bulk download, artifact playback and generation are absent.

## Placement and revision identity

The reusable `Revision artifact downloads` panel is mounted from:

```text
/transcriptions/{job_id}/review
/transcriptions/{job_id}/review/edit
/transcriptions/{job_id}/review/playback
```

The read-only review resolves the latest revision through revision history. Editor and playback use the concrete revision already displayed by those screens.

## Typed metadata

`getRevisionArtifacts(jobId, revisionNumber, signal?)` accepts only complete compatible responses containing safe, unique and deterministically ordered descriptors:

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

Allowed types and metadata are exactly:

```text
MIDI     audio/midi                                  .mid
MusicXML application/vnd.recordare.musicxml+xml      .musicxml
SVG      image/svg+xml                               .svg
```

PDF is rejected and never rendered.

## Verified binary download

`downloadRevisionArtifact` first obtains the authoritative descriptor and then downloads through Spring. Before returning a result it validates:

- HTTP 200;
- Content-Type;
- Content-Disposition safe filename;
- Content-Length when present;
- X-Content-SHA256;
- actual ArrayBuffer length;
- SHA-256 calculated with Web Crypto.

The result is:

```typescript
{
  (blob, filename, mediaType, sizeBytes, sha256);
}
```

No Blob is returned for incompatible bytes or headers.

## Browser save lifecycle

After validation only:

1. create a Blob with the exact media type;
2. create a separate artifact object URL;
3. create a temporary hidden link with `download=filename`;
4. click the link;
5. remove the link;
6. revoke the object URL in `finally`.

This URL is independent from the SAX-044 local audio URL. The Blob and URL are not stored in localStorage, IndexedDB, Cache API, cookies or a service worker. `window.open` is not used.

## UI states

```text
loading
available
not_ready
downloading
downloaded
error
```

A revision without a registered bundle shows:

```text
Artifacts are not available for this revision yet.
```

Each artifact displays type, filename, size, abbreviated SHA and the full SHA as technical text. No false PDF button is shown.

## Accessibility and security

- clear section heading;
- polite loading/downloading/success status;
- focused alert for errors;
- button name includes type and filename;
- only the active artifact button is disabled;
- focus remains on the initiating button after success;
- text-based states, keyboard operation and visible focus;
- responsive list without blue primary treatment or emoji.

The interface states:

```text
Downloads are retrieved through the Saxo product API.
No public storage URL is exposed.
```

No permanence or retention is claimed.

## Limitations

MIDI, MusicXML and SVG download transport is implemented for registered artifacts. Artifact generation from a normal uploaded job remains pending. PDF is not implemented. The pending SAX-043 regeneration request is not executed.
