# TDD iteration 002 — SAX-003

## Scope

Add continuous integration and a single cross-platform quality gate for the AI module. This iteration does not change the service behavior and does not implement SAX-010 or later stories.

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

The contract suite also requires the workflow to invoke Ruff format checking once the runner exists.

## GREEN

Pending.

## REFACTOR

Pending.

## Final verification

Pending.
