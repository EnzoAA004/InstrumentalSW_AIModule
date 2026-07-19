from __future__ import annotations

import importlib.util
import tomllib
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "quality.yml"
QUALITY_SCRIPT_PATH = ROOT / "scripts" / "check_quality.py"
PYPROJECT_PATH = ROOT / "pyproject.toml"
MAKEFILE_PATH = ROOT / "Makefile"
README_PATH = ROOT / "README.md"


def test_quality_workflow_declares_supported_events_and_python_matrix() -> None:
    workflow = load_workflow()

    assert workflow["on"] == {
        "pull_request": {"branches": ["main"]},
        "push": {"branches": ["main"]},
        "workflow_dispatch": None,
    }
    assert set(workflow["jobs"]["quality"]["strategy"]["matrix"]["python-version"]) == {
        "3.11",
        "3.12",
        "3.13",
    }


def test_quality_workflow_uses_minimum_permissions_timeout_and_concurrency() -> None:
    workflow = load_workflow()

    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"]["cancel-in-progress"] is True
    assert "github.event.pull_request.number" in workflow["concurrency"]["group"]
    assert workflow["jobs"]["quality"]["timeout-minutes"] <= 20


def test_quality_workflow_installs_project_and_invokes_single_runner() -> None:
    workflow = load_workflow()
    steps = workflow["jobs"]["quality"]["steps"]

    uses = [step["uses"] for step in steps if "uses" in step]
    commands = [step["run"] for step in steps if "run" in step]

    assert any(action.startswith("actions/checkout@") for action in uses)
    assert any(action.startswith("actions/setup-python@") for action in uses)
    assert 'python -m pip install -e ".[dev]"' in commands
    assert "python scripts/check_quality.py" in commands


def test_cross_platform_runner_contains_all_required_checks() -> None:
    module = load_quality_runner()

    assert commands_from(module) == [
        ("pytest", "--cov=saxo_ai", "--cov-report=term-missing", "--cov-report=xml"),
        ("ruff", "check", "src", "tests", "scripts"),
        ("ruff", "format", "--check", "src", "tests", "scripts"),
        ("mypy",),
    ]


def test_cross_platform_runner_stops_and_propagates_failed_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_quality_runner()
    executed: list[tuple[str, ...]] = []

    class Result:
        returncode = 7

    def fake_run(command: tuple[str, ...], *, check: bool) -> Result:
        assert check is False
        executed.append(command)
        return Result()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.main() == 7
    assert len(executed) == 1


def test_coverage_and_warning_gate_are_centralized_in_pyproject() -> None:
    configuration = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    coverage_run = configuration["tool"]["coverage"]["run"]
    coverage_report = configuration["tool"]["coverage"]["report"]
    pytest_options = configuration["tool"]["pytest"]["ini_options"]

    assert coverage_run["branch"] is True
    assert coverage_report["show_missing"] is True
    assert 90 <= coverage_report["fail_under"] < 100
    assert pytest_options["filterwarnings"] == ["error"]


def test_makefile_delegates_to_cross_platform_runner() -> None:
    makefile = MAKEFILE_PATH.read_text(encoding="utf-8")

    assert "check:\n\tpython scripts/check_quality.py" in makefile
    assert "check: test coverage lint type" not in makefile


def test_readme_documents_single_quality_gate_and_failure_semantics() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "python scripts/check_quality.py" in readme
    assert "Python 3.11, 3.12, and 3.13" in readme
    assert "non-zero exit code" in readme
    for check_name in ("pytest", "coverage", "Ruff lint", "Ruff format", "mypy"):
        assert check_name in readme


def load_workflow() -> dict[str, Any]:
    assert WORKFLOW_PATH.is_file(), f"Missing workflow: {WORKFLOW_PATH.relative_to(ROOT)}"
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert isinstance(workflow, dict)
    return workflow


def load_quality_runner() -> ModuleType:
    assert QUALITY_SCRIPT_PATH.is_file(), (
        f"Missing cross-platform runner: {QUALITY_SCRIPT_PATH.relative_to(ROOT)}"
    )
    spec = importlib.util.spec_from_file_location("check_quality", QUALITY_SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def commands_from(module: ModuleType) -> list[tuple[str, ...]]:
    def normalized_commands() -> Iterator[tuple[str, ...]]:
        for check in module.QUALITY_CHECKS:
            command = tuple(check.command)
            assert command[0] == module.sys.executable
            assert command[1] == "-m"
            yield command[2:]

    return list(normalized_commands())
