# Repository consolidation — Saxo

Audit date: 2026-09-27

## Decision

The canonical repository is:

```text
EnzoAA004/InstrumentalSW_AIModule
```

The repository was chosen because it contains the active AI/FastAPI implementation, the living contracts/TDD documentation, dataset governance, persistence work, queue/worker work, and the current SAX-036 integration branch.

The former Backend and Frontend repositories remain unchanged as read-only migration sources until the owner decides to archive them.

## Canonical branches

| Branch | Purpose | Migrated from | Source commit / snapshot |
|---|---|---|---|
| `main` | Stable AI service + project governance documentation | existing AIModule | `77a9dc7075c0c50e48b7da66557537e3771ee329` |
| `component/ai` | Frozen stable AI snapshot at consolidation time | AIModule `main` | `77a9dc7075c0c50e48b7da66557537e3771ee329` |
| `component/backend` | Spring Boot product gateway | `InstrumentalSW_Backend/main` | source `ba63583fbab88cfd36c4fa3dd8f25ea32ed9cea8` |
| `component/frontend` | Next.js product UI | `InstrumentalSW_Frontend/main` | source `05d83770345731fb945f66e7dbe7bad558727e38` |
| `feature/SAX-036-monophonic-end-to-end-processor` | Current AI integration WIP | AIModule | active PR #29 |

## Migration verification

Before adapting CI triggers, the copied Backend tree in the canonical repository matched the original Backend tree exactly:

```text
1b7e4bb97401de19dd8aed0315531a5948bb8105
```

Before adapting CI triggers, the copied Frontend tree matched the original Frontend tree exactly:

```text
09fac171bff825007d24afb4d2a2e73c742f67da
```

After import, only the branch-specific GitHub Actions trigger was changed so quality runs on the new component branch instead of the old repository's `main`.

## Branch workflow going forward

Do not create new repositories.

AI work:
- start from `main` unless continuing an existing AI feature branch;
- use `feature/SAX-XXX-description`;
- merge back to `main`.

Backend work:
- start from `component/backend`;
- use `backend/SAX-XXX-description`;
- open the PR against `component/backend`.

Frontend work:
- start from `component/frontend`;
- use `frontend/SAX-XXX-description`;
- open the PR against `component/frontend`.

The old repositories are migration sources only. Do not apply new product changes to them.

## Why branches instead of a directory monorepo

The user explicitly chose one GitHub repository with the three codebases separated by branches. This keeps each ecosystem independent:

- Python / FastAPI / Alembic / pytest;
- Java 21 / Spring Boot / Maven;
- Next.js / TypeScript / npm.

It also avoids mixing three dependency graphs and three unrelated build roots while still giving one canonical GitHub repository.

## Manual repository administration left to the owner

These operations are intentionally not required for code correctness:

1. optionally rename `InstrumentalSW_AIModule` to a neutral name such as `InstrumentalSW` or `Saxo`;
2. after the migration has been used successfully, archive the old Backend and Frontend repositories;
3. update local Git remotes/clones to the canonical repository;
4. configure branch protection/rulesets for `main`, `component/backend`, and `component/frontend`;
5. add deployment secrets/credentials only through GitHub/environment secret stores, never in the repository.

GitHub normally redirects old repository URLs after a rename, but application/deployment configuration should still be reviewed explicitly.
