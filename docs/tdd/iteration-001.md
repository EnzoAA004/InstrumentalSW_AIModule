# TDD iteration 001 — SAX-000

## Scope

Initialize `EnzoAA004/InstrumentalSW_AIModule` from the documented Saxo starter while preserving only the existing minimal contracts. Backend and Frontend are outside this iteration.

## RED

The starter behavior tests were committed before production code. The first execution failed during collection as expected:

```text
ModuleNotFoundError: No module named 'saxo_ai'
pytest exit code: 4
```

A second packaging check reproduced an editable-build failure caused by Hatchling's automatic editable detection. A project-local `dev-mode-dirs = ["src"]` configuration removed that hidden dependency.

A warning gate (`filterwarnings = ["error"]`) then reproduced a FastAPI/Starlette TestClient compatibility warning. FastAPI was constrained to the compatible starter range `<0.139`.

## GREEN

The minimum implementation introduced:

- FastAPI composition root and three starter endpoints;
- domain enums, job entity, and saxophone transposition rule;
- application use cases and repository protocol;
- in-memory infrastructure adapter;
- validation for extension and empty content;
- Hatchling `src` package configuration.

No audio decoding, FFmpeg, hashing, model inference, training, persistence, queues, cloud storage, or datasets were added.

## REFACTOR

Responsibilities were separated into `api`, `application`, `domain`, and `infrastructure`. API responses are transport schemas, use cases do not depend on FastAPI, and the in-memory repository implements an application port.

## Final verification

```text
python -m pip install -e ".[dev]"                         PASS
python -m pytest                                          18 passed
python -m pytest --cov=saxo_ai --cov-report=term-missing  100% (123 statements, 8 branches)
python -m ruff check src tests                            All checks passed
python -m mypy                                            Success: no issues found in 18 source files
uvicorn smoke test /health                                HTTP 200 {"status": "ok"}
```
