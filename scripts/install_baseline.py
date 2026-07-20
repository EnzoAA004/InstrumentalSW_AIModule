"""Install and verify the fully pinned optional FiloSax baseline runtime."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from saxo_ai.infrastructure.hf_baseline_contract import RuntimeDistributionRequirement

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
RUNTIME_DEPENDENCIES = (
    "torch>=1.9.0",
    "librosa>=0.9.0",
    "huggingface-hub>=0.16.0",
    "numpy>=1.21.0",
    "safetensors>=0.3.0",
    "matplotlib",
    "mido",
    "torchlibrosa",
)


def _ensure_source_path() -> None:
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))


def runtime_requirements() -> tuple[RuntimeDistributionRequirement, ...]:
    _ensure_source_path()
    from saxo_ai.infrastructure.hf_baseline_contract import BASELINE_RUNTIME_REQUIREMENTS

    return BASELINE_RUNTIME_REQUIREMENTS


def verify_installed_runtime() -> dict[str, str]:
    _ensure_source_path()
    from saxo_ai.infrastructure.hf_runtime import verify_baseline_runtime

    return verify_baseline_runtime()


def vcs_requirement(package_name: str, source_url: str, source_revision: str) -> str:
    return f"{package_name} @ git+{source_url}@{source_revision}"


def install_commands() -> tuple[tuple[str, ...], ...]:
    python = sys.executable
    pip = (python, "-m", "pip", "install", "--no-cache-dir")
    baseline, piano = runtime_requirements()
    return (
        (*pip, "-e", f"{ROOT}[dev]"),
        (*pip, *RUNTIME_DEPENDENCIES),
        (
            *pip,
            "--no-deps",
            vcs_requirement(
                piano.package_name,
                piano.source_url,
                piano.source_revision,
            ),
        ),
        (
            *pip,
            "--no-deps",
            vcs_requirement(
                baseline.package_name,
                baseline.source_url,
                baseline.source_revision,
            ),
        ),
    )


def run_command(command: tuple[str, ...]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(command, check=False)


def main(*, python_version: tuple[int, int] | None = None) -> int:
    active_version = python_version or sys.version_info[:2]
    if active_version != (3, 11):
        print("The pinned FiloSax baseline is validated only on Python 3.11.", file=sys.stderr)
        return 2

    for command in install_commands():
        result = run_command(command)
        if result.returncode != 0:
            return result.returncode

    _ensure_source_path()
    from saxo_ai.application.transcription_errors import TranscriptionEngineUnavailableError

    try:
        verified = verify_installed_runtime()
    except TranscriptionEngineUnavailableError as error:
        print(str(error), file=sys.stderr)
        return 1

    for requirement in runtime_requirements():
        print(
            f"Verified {requirement.package_name} "
            f"version={verified[requirement.package_name]} "
            f"source_revision={requirement.source_revision}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
