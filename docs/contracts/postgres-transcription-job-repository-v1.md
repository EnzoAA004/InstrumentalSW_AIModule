# Postgres transcription-job repository — v1

## Objective

SAX-070 replaces in-process, restart-losing state with a real, migrated
Postgres-backed implementation for one repository — `TranscriptionJobRepository`
— establishing the reusable persistence pattern (engine, Alembic migrations,
strict domain⇄row mapping, real-database integration tests) that the
remaining repositories will follow.

## Scope: why only the job repository

`TranscriptionJob` is the simplest, most central aggregate (flat fields, no
nested collections) and the natural first slice. `TranscriptionReview`,
`TranscriptionRevision`/`RegenerationRequest`, and `RevisionArtifactBundle`
each carry nested note-event/artifact-binary data that deserve their own
focused stories rather than being rushed through in one sitting under the
same schema-design rigor. They are **not done yet** — `main.py` still
defaults every other repository to its `InMemory*` implementation. Do not
claim jobs "survive a restart end-to-end"; only the job record does.

## Traceability

```text
SAX-070
→ TranscriptionJobRepository (existing Protocol, application/ports.py)
→ SAXO_DATABASE_URL / load_database_url
→ build_postgres_engine
→ transcription_jobs (SQLAlchemy Core table)
→ PostgresTranscriptionJobRepository
→ migrations/versions/0001_create_transcription_jobs.py
→ tests/unit/test_postgres_configuration.py
→ tests/integration/test_postgres_transcription_job_repository.py (real Postgres via testcontainers)
```

## Configuration

```text
SAXO_DATABASE_URL   postgresql(+psycopg)://user:pass@host:port/db  (required, no default)
```

`load_database_url` raises `PostgresConfigurationError` if unset, blank, or
not a `postgresql` URL — there is no silent fallback to SQLite or any other
engine. The default `app = create_app()` in `main.py` is unchanged and
remains fully in-memory; nothing requires a database to boot. An operator
opts in explicitly:

```python
from sqlalchemy import create_engine
from saxo_ai.infrastructure.postgres_transcription_job_repository import (
    PostgresTranscriptionJobRepository,
)

engine = create_engine(load_database_url())
app = create_app(job_repository=PostgresTranscriptionJobRepository(engine))
```

## Migrations

Alembic lives at the repo root (`alembic.ini`, `migrations/`) so it can
target the same `SAXO_DATABASE_URL` the application uses.
`migrations/env.py` imports `saxo_ai.infrastructure.postgres_schema.metadata`
directly — there is no separate, hand-maintained schema description to drift
from the `Table` definition the repository uses.

```bash
python -m alembic upgrade head
```

Revision `0001` creates `transcription_jobs` with one row per job
(`job_id` primary key) and no foreign keys yet, since no other table exists.

## Repository behavior

`PostgresTranscriptionJobRepository.save` is an upsert
(`INSERT ... ON CONFLICT (job_id) DO UPDATE`), matching the existing
in-memory repository's `save` semantics (`dict[job_id] = job`, silently
replacing). `get` returns `None` for a missing row, never raises.

Domain⇄row mapping is explicit (`_row_from_job` / `_job_from_row`), no ORM
entity duplicating the domain dataclass — consistent with this project's
existing JSON-codec pattern (SAX-050/051/052) of keeping `saxo_ai.domain`
free of infrastructure concerns.

## Testing

Integration tests are marked `postgres_integration` and use
`testcontainers[postgres]` to start a real, ephemeral `postgres:16-alpine`
container, run `alembic upgrade head` as a subprocess against it, then
exercise the repository — no mocks, per this project's rule against mocking
integration-level infrastructure. This requires a working Docker daemon;
GitHub-hosted `ubuntu-latest` runners provide one by default, so CI needs no
workflow changes. Locally, Docker Desktop (or an equivalent daemon) must be
running, or these tests fail to start a container — they are not silently
skipped in that case, since `pytest.importorskip` only guards the
`testcontainers` *import*, not Docker availability.

## Architecture

```text
domain
  TranscriptionJob (existing, unchanged) — no persistence knowledge.

infrastructure
  postgres_configuration.py  — env-var loading, no default DB.
  postgres_engine.py         — pooled, pre-ping SQLAlchemy Engine factory.
  postgres_schema.py         — SQLAlchemy Core Table (single source of
                                schema truth, shared with Alembic).
  postgres_transcription_job_repository.py — Protocol-conformant adapter.

migrations/
  Alembic, targeting postgres_schema.metadata.
```

## Deferred to fast-follow work (same pattern, not yet built)

- `TranscriptionReviewRepository`, `TranscriptionRevisionRepository`,
  `RegenerationRequestRepository`, `RevisionArtifactRepository` — Postgres
  adapters following this exact shape.
- `TranscriptionReviewRegistrationRepository` currently hard-requires the
  in-memory review/revision repositories via an `isinstance` check in
  `main.py::_registration_repository`; a Postgres-backed registration
  repository (or relaxing that check) is required before jobs, reviews, and
  revisions can all persist together.
- Connection pooling/retry tuning for production load, and
  `SAXO_REQUIRE_POSTGRES`-style CI gating analogous to
  `SAXO_REQUIRE_FFMPEG`/`SAXO_REQUIRE_BASELINE`, are both out of scope here.
