"""Run the complete InstrumentalSW AI-module quality gate."""

from __future__ import annotations

import subprocess
import sys
from typing import NamedTuple


class QualityCheck(NamedTuple):
    """One named command in the local and CI quality pipeline."""

    name: str
    command: tuple[str, ...]


QUALITY_CHECKS: tuple[QualityCheck, ...] = (
    QualityCheck(
        "pytest with statement and branch coverage",
        (
            sys.executable,
            "-m",
            "pytest",
            "--cov=saxo_ai",
            "--cov-report=term-missing",
            "--cov-report=xml",
        ),
    ),
    QualityCheck(
        "Ruff lint",
        (sys.executable, "-m", "ruff", "check", "src", "tests", "scripts"),
    ),
    QualityCheck(
        "Ruff format check",
        (
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--check",
            "src",
            "tests",
            "scripts",
        ),
    ),
    QualityCheck("mypy strict type analysis", (sys.executable, "-m", "mypy")),
)


def main() -> int:
    """Run checks sequentially and return the first failing exit code."""
    for index, check in enumerate(QUALITY_CHECKS, start=1):
        print(f"[{index}/{len(QUALITY_CHECKS)}] {check.name}", flush=True)
        result = subprocess.run(check.command, check=False)
        if result.returncode != 0:
            print(
                f"Quality gate stopped: {check.name} failed with exit code {result.returncode}.",
                file=sys.stderr,
                flush=True,
            )
            return result.returncode

    print("Quality gate passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
