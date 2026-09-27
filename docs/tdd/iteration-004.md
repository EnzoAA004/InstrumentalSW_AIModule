# TDD iteration 004 — SAX-043 revision gateway

## Scope

This iteration adds the Spring Boot gateway for immutable transcription revisions after SAX-042.

Exact branch base:

```text
9fd901c8596a7905dc414c0954d87130f30a9d24
```

That commit is the squash result of Backend SAX-042 PR #3.

## RED

Tests were committed before production revision records, gateway client, configuration, or controller:

```text
test(SAX-043): define revision gateway contract
test(SAX-043): define revision API forwarding and errors
test(SAX-043): define product revision endpoints and error mapping
test(SAX-043): add deterministic revision web fixture
```

The tests defined:

- four independent application gateway operations;
- exact public and FastAPI paths;
- bodyless GET and regeneration POST;
- exact revision-operation JSON;
- complete history/detail/request parsing;
- stable 400/404/409/422/502 mapping;
- timeout and refused connection;
- malformed or incompatible successful JSON;
- browser CORS for GET/POST;
- no Spring persistence.

A real JDK `HttpServer` captures method, raw path, and body. Mock-only transport was not used as the integration proof.

## GREEN

Production added:

```text
domain revision records and enums
application revision commands and use cases
TranscriptionRevisionGateway
FastApiTranscriptionRevisionClient
RevisionConfiguration
TranscriptionRevisionController
public response DTOs
stable revision error codes
```

Spring validates both incoming browser commands and complete AI-service responses. The controller forwards one request; the infrastructure adapter owns internal HTTP transport and upstream compatibility validation.

## REFACTOR

Refactoring:

- kept the new gateway separate from upload/status/review gateways;
- centralized command parsing and response-field validation;
- preserved public error envelopes without upstream leakage;
- used immutable Java records and copied lists;
- applied pinned Spotless output;
- corrected deterministic fixtures after formatting;
- retained the existing CORS configuration and all quality thresholds.

A temporary feature-branch formatter workflow applied exact Spotless output and was removed before the final diff.

## Quality

The normal protected command is:

```bash
./mvnw verify
```

It runs unit, MVC, and real HTTP tests, Spotless, Checkstyle, and the JaCoCo line gate. Final run identifiers and exact coverage are recorded in the PR body after documentation is complete.

No threshold or protected workflow was modified.

## Architecture and persistence

```text
Next.js
→ TranscriptionRevisionController
→ revision use cases
→ TranscriptionRevisionGateway
→ FastApiTranscriptionRevisionClient
→ existing FastAPI revision endpoints
```

Spring has no revision repository. History, events, and regeneration requests remain request-scoped DTOs.

## Remaining boundary

Editing, validation and revision history are implemented.

A regeneration request is recorded explicitly.

Artifact execution remains pending; Spring neither calls exporters nor reports completion.
