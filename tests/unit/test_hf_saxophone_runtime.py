from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from saxo_ai.infrastructure.hf_runtime import _HfMidiRuntime


class WarningModel:
    def __init__(self, message: str) -> None:
        self.message = message

    def transcribe(
        self,
        audio_path: Path,
        midi_path: Path,
        *,
        activations: bool,
    ) -> tuple[Path, dict[str, object]]:
        warnings.warn(self.message, DeprecationWarning, stacklevel=2)
        return midi_path, {"events": []}


@pytest.mark.parametrize("module_name", ["aifc", "audioop", "sunau"])
def test_runtime_suppresses_only_known_audioread_stdlib_deprecations(
    module_name: str,
    tmp_path: Path,
) -> None:
    runtime = _HfMidiRuntime(
        WarningModel(
            f"'{module_name}' is deprecated and slated for removal in Python 3.13"
        )
    )
    assert runtime.transcribe(
        audio_path=tmp_path / "canonical.wav",
        midi_path=tmp_path / "baseline.mid",
    ) == {"events": []}


def test_runtime_does_not_hide_unrelated_deprecation_warnings(tmp_path: Path) -> None:
    runtime = _HfMidiRuntime(WarningModel("unrelated baseline deprecation"))
    with pytest.raises(DeprecationWarning, match="unrelated"):
        runtime.transcribe(
            audio_path=tmp_path / "canonical.wav",
            midi_path=tmp_path / "baseline.mid",
        )
