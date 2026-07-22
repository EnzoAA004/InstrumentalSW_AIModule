# TDD iteration 019 — Revision artifact downloads

## Story boundary

SAX-045 introduces read-only list/download transport for MIDI, MusicXML and SVG artifacts that have already been materialized and registered for a concrete transcription revision.

It does not implement PDF, automatic upload processing, regeneration execution, a worker, queue, persistence or SAX-050.

## Exact base

```text
f00ca349d97d45f9a9a9f0a3e01d15b2b8f11cac
feature/SAX-045-artifact-download-api
```

## RED

Tests preceded production:

```text
619a41f test(SAX-045): define revision artifact bundle contracts
136ed37 test(SAX-045): define artifact repository and internal registration
b879693 test(SAX-045): define artifact list and binary download API
5339bcc test(SAX-045): define artifact not-ready and real exporter registration
```

The RED suite referenced missing domain contracts, repository/use cases, API routes and application composition after successful dependency setup. Installation failure was not used as RED.

## GREEN

Minimal production added:

- immutable artifact descriptors, artifacts and bundles;
- safe IDs, filenames, media types and extensions;
- exact size and SHA-256 validation;
- separate in-memory repository with idempotency/conflict;
- internal registration and read use cases;
- metadata list and binary GET routes;
- private/no-store security headers;
- stable unknown/not-ready/missing errors;
- application composition without a public write route.

The real integration fixture executes existing MIDI, MusicXML and Verovio SVG capabilities before registration. GET handlers only query the repository.

## REFACTOR

Checksum calculation moved outside the domain package to preserve the established architecture rule while retaining exact byte/digest validation. Fixtures were strictly typed, remaining validation branches were covered and pinned Ruff formatting was applied. No quality threshold or protected workflow changed.

Temporary diagnostic/formatter workflows were removed before the final tree.

## Test matrix

- valid and invalid bundles;
- duplicate IDs, filenames and order;
- unsafe filenames and IDs;
- incompatible type/media/extension;
- exact size and SHA;
- immutable bytes;
- idempotency and incompatible replacement;
- unknown job/revision, not-ready bundle and missing artifact;
- list without bytes/base64;
- exact binary content and headers;
- no public artifact write endpoint;
- no exporter call during GET;
- real MIDI, MusicXML and multiple SVG-page registration;
- full regression suite and real Python 3.11 baseline.

## Protected quality invariants

The protected matrix remains unchanged and continues to run Python 3.11, 3.12 and 3.13. Python 3.11 installs and executes the real pinned baseline. The workflow blob remains:

```text
62f8ce2737a78081a37397b1e8b7a095c00fc1b7
```

The quality runner still enforces at least 90% total coverage, Ruff lint, Ruff format and strict mypy. No SAX-045-specific exclusion or threshold reduction was introduced.

## Traceability

```text
SAX-045
→ registered RevisionArtifactBundle
→ RevisionArtifactRepository
→ ListRevisionArtifacts / GetRevisionArtifact
→ FastAPI list/download tests
```

## Honest status

Download transport is implemented for already-materialized artifacts. Normal upload-to-artifact execution remains pending. PDF is not implemented.
