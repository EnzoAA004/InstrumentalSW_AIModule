from __future__ import annotations

import subprocess
import sys
from pathlib import Path

COMMANDS = {
    "quality": [sys.executable, "scripts/check_quality.py"],
    "pytest": [sys.executable, "-m", "pytest"],
    "not-integration": [sys.executable, "-m", "pytest", "-m", "not integration"],
    "integration": [sys.executable, "-m", "pytest", "-m", "integration"],
    "midi-integration": [sys.executable, "-m", "pytest", "-m", "midi_integration"],
    "baseline-integration": [sys.executable, "-m", "pytest", "-m", "baseline_integration"],
    "coverage": [
        sys.executable,
        "-m",
        "pytest",
        "--cov=saxo_ai",
        "--cov-report=term-missing",
        "--cov-report=xml",
    ],
    "ruff-lint": [sys.executable, "-m", "ruff", "check", "src", "tests", "scripts"],
    "ruff-format": [
        sys.executable,
        "-m",
        "ruff",
        "format",
        "--check",
        "src",
        "tests",
        "scripts",
    ],
    "mypy": [sys.executable, "-m", "mypy"],
}


def main() -> int:
    output = Path("sax032-command-metrics")
    output.mkdir(exist_ok=True)
    first_failure = 0
    for name, command in COMMANDS.items():
        completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (output / f"{name}.log").write_text(completed.stdout, encoding="utf-8")
        (output / f"{name}.exit").write_text(f"{completed.returncode}\n", encoding="utf-8")
        if first_failure == 0 and completed.returncode != 0:
            first_failure = completed.returncode
    return first_failure


if __name__ == "__main__":
    raise SystemExit(main())
