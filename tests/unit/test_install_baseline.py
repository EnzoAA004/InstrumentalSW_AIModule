from __future__ import annotations

import sys

import pytest
from scripts import install_baseline

from saxo_ai.infrastructure import hf_baseline_contract as contract


class Result:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode


def test_install_commands_use_current_python_no_cache_and_exact_commits() -> None:
    commands = install_baseline.install_commands()

    assert len(commands) == 4
    assert all(command[:4] == (sys.executable, "-m", "pip", "install") for command in commands)
    assert all("--no-cache-dir" in command for command in commands)
    assert commands[0][-2] == "-e"
    assert commands[1][-len(install_baseline.RUNTIME_DEPENDENCIES) :] == (
        install_baseline.RUNTIME_DEPENDENCIES
    )
    assert "--no-deps" in commands[2]
    assert "--no-deps" in commands[3]
    assert "--force-reinstall" in commands[2]
    assert "--force-reinstall" in commands[3]
    assert commands[2][-1].endswith("@" + contract.PIANO_TRANSCRIPTION_SOURCE_REVISION)
    assert commands[3][-1].endswith("@" + contract.BASELINE_SOURCE_REVISION)


def test_installer_runs_commands_without_shell_and_verifies_pep610(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executed: list[tuple[str, ...]] = []

    def run(command: tuple[str, ...]) -> Result:
        executed.append(command)
        return Result(0)

    verified = {
        contract.BASELINE_PACKAGE_NAME: contract.BASELINE_PACKAGE_VERSION,
        contract.PIANO_TRANSCRIPTION_PACKAGE_NAME: contract.PIANO_TRANSCRIPTION_PACKAGE_VERSION,
    }
    monkeypatch.setattr(install_baseline, "run_command", run)
    monkeypatch.setattr(install_baseline, "verify_installed_runtime", lambda: verified)

    assert install_baseline.main(python_version=(3, 11)) == 0
    assert executed == list(install_baseline.install_commands())


def test_installer_propagates_first_failed_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def run(command: tuple[str, ...]) -> Result:
        nonlocal calls
        calls += 1
        return Result(17)

    monkeypatch.setattr(install_baseline, "run_command", run)

    assert install_baseline.main(python_version=(3, 11)) == 17
    assert calls == 1


def test_installer_rejects_unsupported_python_without_running_pip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        install_baseline,
        "run_command",
        lambda *args, **kwargs: pytest.fail("pip must not run"),
    )

    assert install_baseline.main(python_version=(3, 12)) == 2
