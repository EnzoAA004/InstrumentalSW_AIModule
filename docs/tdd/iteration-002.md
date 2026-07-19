# TDD iteration 002 — SAX-003

## Scope

Add continuous integration and a single cross-platform quality gate for the AI module. This iteration does not change service behavior and does not implement SAX-010 or later stories.

## RED

Quality-system contract tests were added before the workflow, runner, coverage threshold, formatting check, or documentation changes.

Command:

```text
python -m pytest tests/quality/test_quality_configuration.py
```

Exact result:

```text
collected 8 items
8 failed in 0.46s
RED_EXIT_CODE=1
```

The failures demonstrated the expected missing contracts:

```text
Missing workflow: .github/workflows/quality.yml
Missing cross-platform runner: scripts/check_quality.py
KeyError: 'fail_under'
Makefile did not delegate to python scripts/check_quality.py
README did not document the single quality gate
```

The contract suite also required the future runner to invoke Ruff format checking.

During GREEN, the first complete quality-gate execution exposed a strict-mypy failure:

```text
tests/quality/test_quality_configuration.py:11: error: Library stubs not installed for "yaml"  [import-untyped]
Found 1 error in 1 file
```

A new test was written first and failed with:

```text
assert "types-pyyaml" in normalized
BUG_RED_EXIT_CODE=1
```

Only then was `types-PyYAML` added to the development dependencies.

## GREEN

The minimum implementation added:

- `.github/workflows/quality.yml` for pull requests to `main`, pushes to `main`, and manual dispatch;
- Python 3.11, 3.12, and 3.13 matrix jobs;
- `actions/checkout@v6` and `actions/setup-python@v6` with pip caching;
- minimum `contents: read` permissions;
- concurrency cancellation and a 15-minute timeout;
- `scripts/check_quality.py` as the single Windows/Unix entry point;
- pytest coverage with XML output and an explicit 90% threshold;
- Ruff lint and Ruff format checking;
- strict mypy checking;
- explicit YAML runtime and typing dependencies.

## REFACTOR

Quality configuration is centralized instead of duplicated:

- CI installs the project and invokes `python scripts/check_quality.py`;
- `make check` delegates to the same Python runner;
- coverage threshold and warning policy remain in `pyproject.toml`;
- the runner uses `sys.executable`, avoids `shell=True`, prints each control, stops on the first failure, and propagates its exit code.

## Final local verification

```text
python -m pip install -e ".[dev]"
Successfully built instrumentalsw-ai-module
Successfully installed instrumentalsw-ai-module-0.1.0

python scripts/check_quality.py
27 passed
TOTAL: 123 statements, 0 missed; 8 branches, 0 partial; 100%
Required test coverage of 90.0% reached
All checks passed!
20 files already formatted
Success: no issues found in 20 source files
Quality gate passed.

python -m pytest
27 passed in 0.52s

python -m pytest --cov=saxo_ai --cov-report=term-missing --cov-report=xml
27 passed in 0.88s
Coverage XML written to file coverage.xml
Total coverage: 100.00%

python -m ruff check src tests scripts
All checks passed!

python -m ruff format --check src tests scripts
20 files already formatted

python -m mypy
Success: no issues found in 20 source files

python -m uvicorn saxo_ai.main:app
GET /health -> HTTP 200 {"status": "ok"}
```

## Repository administration notes

- SAX-000 PR #1 was marked ready and squash-merged into `main` as commit `e4217afac821d141bc095709148b4756949e2eae`.
- The execution environment has no `gh` binary and no direct GitHub network resolution. The connector exposes no delete-ref or branch-protection/ruleset action, so remote branch deletion and `main` protection cannot be applied through the available tools. These limitations must be reported precisely rather than simulated.
