# TDD iteration 006 — Revision artifact downloads

## Exact base

```text
3fd9d5f07a002c0a9ff7b17d59c7074fc91ddd71
feature/SAX-045-artifact-downloads
```

## RED

Tests preceded production:

```text
f485a67 test(SAX-045): define typed artifact metadata client
1e2190f test(SAX-045): define verified binary download client
e04a429 test(SAX-045): define accessible artifact download panel
9b0ee63 test(SAX-045): define download URL cleanup
5b47bed test(SAX-045): define navigation integration
```

The protected workflow reached Vitest and failed because the artifact client, verified binary transport, Blob lifecycle and panel did not exist. Dependency setup was not used as RED.

## GREEN

Production added:

- complete typed artifact descriptors and listing validation;
- Spring-only metadata and binary clients;
- Web Crypto SHA-256 and size verification;
- safe Content-Disposition validation;
- verified Blob result;
- temporary anchor/object URL save lifecycle;
- accessible reusable panel with honest not-ready state;
- latest-revision resolver for the read-only review;
- concrete revision integration in editor and playback;
- responsive styling and privacy/security language.

## REFACTOR

Artifact panel effects were isolated from legacy fixtures that explicitly inject alternate screen clients, while remaining enabled by default in production. Download status text was separated from button text, latest-revision resolution became directly testable and invalid metadata/transport branches were covered instead of lowering coverage.

Exact ArrayBuffer/Web Crypto fixtures and deterministic temporary-link cleanup are used. Temporary refactor/fixture workflows were removed before the final tree.

## Test matrix

- complete metadata and public errors;
- MIDI, MusicXML, one/multiple SVG pages and no PDF;
- unsafe IDs/filenames, incompatible media/extensions, duplicate order;
- verified bytes, size, SHA and headers;
- Web Crypto unavailable;
- Backend unavailable and abort;
- loading, available, not-ready, downloading, downloaded and error;
- Blob media type;
- object URL creation/click/removal/revocation including error cleanup;
- no FastAPI URL, window.open or browser persistence;
- integration from review, editor and playback;
- accessible heading, live status, focused alerts, named buttons and keyboard operation;
- full SAX-040 through SAX-044 regressions.

## Traceability

```text
SAX-045
→ typed descriptor/list tests
→ verified binary client tests
→ reusable accessible panel tests
→ browser Blob/object URL lifecycle tests
→ review/editor/playback integration tests
```

## Honest status

Download transport is implemented for already-materialized artifacts. Normal upload-to-artifact execution remains pending. PDF is not implemented.
