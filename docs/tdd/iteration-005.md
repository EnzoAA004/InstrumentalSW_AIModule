# TDD iteration 005 — Revision artifact download gateway

## Exact base

```text
67c2c83f0e23cdc3661fb3c938c0a58b7ffa9bcd
feature/SAX-045-artifact-download-gateway
```

## RED

Tests-only commits defined production contracts before implementation:

```text
f57415a test(SAX-045): define artifact gateway contracts
0a5c617 test(SAX-045): define artifact metadata forwarding
2e45471 test(SAX-045): define public artifact endpoints and errors
b1d58a3 test(SAX-045): define binary download validation
```

The normal workflow failed at test compilation because the new port, use cases, domain records, client and controller did not exist. Dependency setup succeeded, so this was functional RED.

## GREEN

Production introduced:

- validated artifact type, descriptor, list and binary records;
- a separate `TranscriptionArtifactGateway`;
- list/download application use cases;
- a real `RestClient` adapter with configured timeouts;
- descriptor-first binary verification;
- exact public list/download endpoints and headers;
- stable artifact errors and product API mapping;
- bean composition with no Spring persistence.

## REFACTOR

Tests were expanded for timeout, refused connection, stable 400/404/409 mapping, 5xx, malformed payload and unexpected status. Pinned Spotless formatting was applied. No quality threshold, Checkstyle rule, JaCoCo gate or protected workflow changed.

Temporary formatter workflows were removed before the final tree.

## Test matrix

- exact routes, methods and bodyless GET;
- complete descriptor forwarding;
- UUID/revision identity;
- safe ID and filename;
- MIDI/MusicXML/SVG metadata rules;
- unique deterministic order;
- binary Content-Type and Content-Disposition;
- optional Content-Length and actual size;
- SHA header and locally calculated SHA-256;
- exact byte forwarding;
- 400, 404, 409 and 5xx;
- timeout and connection refusal;
- malformed JSON and incompatible binary responses;
- public controller headers;
- read-only methods;
- full upload/status/review/revision regressions.

## Architecture and limitations

```text
TranscriptionArtifactController
→ application use cases
→ TranscriptionArtifactGateway
→ FastApiTranscriptionArtifactClient
```

No repository, database, cache, filesystem, object storage, PDF, ZIP, generation, regeneration execution, worker, queue, BackgroundTasks or SAX-050 is included.

Download transport is implemented for already-materialized artifacts. Normal upload-to-artifact execution remains pending. PDF is not implemented.
