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

### Bug RED — typed YAML parsing

The first complete local gate exposed a strict-mypy failure:

```text
tests/quality/test_quality_configuration.py:11: error: Library stubs not installed for "yaml"  [import-untyped]
Found 1 error in 1 file
```

A dependency contract was written first and failed because `types-PyYAML` was missing. The stubs were added only after that reproducing test.

### Bug RED — current Starlette test client

The first GitHub Actions matrix failed during pytest collection on Python 3.11, 3.12, and 3.13:

```text
starlette.exceptions.StarletteDeprecationWarning:
Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
Quality gate stopped: pytest with statement and branch coverage failed with exit code 4.
```

Because pytest warnings are errors, a dependency contract was written before adding `httpx2`.

### Bug RED — response typing compatibility

After installing `httpx2`, tests, coverage, and Ruff passed remotely, but strict mypy reproduced a concrete incompatibility:

```text
tests/api/test_transcriptions.py:113: error:
Incompatible return value type
(got "httpx2._models.Response", expected "httpx._models.Response")  [return-value]
Found 1 error in 1 file (checked 20 source files)
```

A contract was added first to reject direct `httpx` or `httpx2` response imports in API test helpers and to reject the legacy `httpx` development dependency.

## GREEN

The minimum implementation added:

- `.github/workflows/quality.yml` for pull requests to `main`, pushes to `main`, and manual dispatch;
- Python 3.11, 3.12, and 3.13 matrix jobs;
- `actions/checkout@v6` and `actions/setup-python@v6` with pip caching;
- minimum `contents: read` permissions;
- concurrency cancellation and a 15-minute timeout;
- `scripts/check_quality.py` as the single Windows/Unix entry point;
- pytest statement and branch coverage with XML output and an explicit 90% threshold;
- Ruff lint and Ruff format checking;
- strict mypy checking;
- explicit YAML runtime and typing dependencies;
- the current Starlette `httpx2` test dependency;
- a structural `ResponseLike` protocol that avoids coupling tests to either HTTP client implementation.

## REFACTOR

Quality configuration is centralized instead of duplicated:

- CI installs the project and invokes `python scripts/check_quality.py`;
- `make check` delegates to the same Python runner;
- coverage threshold and warning policy remain in `pyproject.toml`;
- the runner uses `sys.executable`, avoids `shell=True`, prints each control, stops on the first failure, and propagates its exit code;
- temporary diagnostic artifact steps were removed from the final workflow;
- API test helpers depend only on the response behavior they consume.

## Final local verification

Environment: Python 3.13.5.

```text
python -m pip install -e ".[dev]"
Successfully built instrumentalsw-ai-module
Successfully installed instrumentalsw-ai-module-0.1.0

python scripts/check_quality.py
28 passed in 1.06s
TOTAL: 123 statements, 0 missed; 8 branches, 0 partial; 100%
Required test coverage of 90.0% reached
All checks passed!
20 files already formatted
Success: no issues found in 20 source files
Quality gate passed.

python -m pytest
28 passed in 0.49s

python -m pytest --cov=saxo_ai --cov-report=term-missing --cov-report=xml
28 passed in 0.91s
Coverage XML written to file coverage.xml
Required test coverage of 90.0% reached. Total coverage: 100.00%

python -m ruff check src tests scripts
All checks passed!

python -m ruff format --check src tests scripts
20 files already formatted

python -m mypy
Success: no issues found in 20 source files

python -m uvicorn saxo_ai.main:app
GET /health -> HTTP 200 {"status":"ok"}
```

## Final GitHub Actions verification

Final clean workflow run: `29695369050`.

```text
Python 3.11 — success
Python 3.12 — success
Python 3.13 — success
```

A superseded intermediate execution was cancelled by the configured concurrency group, confirming `cancel-in-progress` behavior.

## Repository administration notes

- SAX-000 PR #1 was marked ready and squash-merged into `main` as commit `e4217afac821d141bc095709148b4756949e2eae`.
- The SAX-000 remote branch still resolves. The GitHub connector exposes no delete-ref action, `gh` is unavailable, and direct GitHub network access is blocked, so it could not be deleted safely from this environment.
- The available connector exposes no branch-protection or ruleset write action. Protection of `main` therefore remains a documented manual step rather than a simulated success.
- Exact required check names are `Python 3.11`, `Python 3.12`, and `Python 3.13`.
- Recommended ruleset: target `main`; require a pull request; require all three checks; require the branch to be up to date when GitHub permits it; do not enable auto-merge; keep an owner bypass to avoid an impossible permanent lockout.
