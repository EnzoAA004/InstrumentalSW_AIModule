# TDD iteration 023 — PostgreSQL review/revision persistence

## Story boundary

SAX-076 replaces process-local storage for transcription review, immutable revision history, revision events and regeneration requests with PostgreSQL-backed repositories.

Jobs, original audio, processing queue and revision artifact bytes/metadata already have separate persistence stories. This iteration does not add the production composition root, worker executable, regeneration execution, auth, retention, source separation, multiinstrument behavior or Backend/Frontend changes.

## Exact base

```text
f391941c81c1de3cff5ccbc04c582ce0e3651b74
feature/SAX-076-postgres-review-revision-persistence
```

## RED

The first RED test file is:

```text
tests/integration/test_postgres_review_revision_persistence.py
```

It defines the required durable behavior before the adapter exists:

- review + revision zero survive new repository instances;
- revision-zero initialization is transactional;
- revision histories are immutable, sequential and reject stale writers;
- regeneration requests are durable and idempotent;
- database constraints reject orphan records;
- duplicate initialization is idempotent while incompatible review registration is rejected.

Initial RED result:

```text
ModuleNotFoundError: No module named 'saxo_ai.infrastructure.postgres_review_revision_repository'
```

## GREEN

Implemented:

- migration `0004_create_review_revision_persistence.py`;
- SQLAlchemy tables in `postgres_schema.py`;
- PostgreSQL repositories in `postgres_review_revision_repository.py`;
- integration coverage for durability, transactionality, optimistic revision append and idempotent regeneration requests.

Local PostgreSQL integration execution is blocked in this Windows sandbox by Docker npipe support requiring `pypiwin32`, before the test database starts.

## REFACTOR

The adapter keeps SQL serialization in infrastructure helpers and does not change application ports or the production composition root. Production wiring remains the SAX-077 boundary.
