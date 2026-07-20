from __future__ import annotations

import json
import re
import warnings
from importlib import import_module, metadata
from pathlib import Path
from typing import Protocol, cast

from saxo_ai.application.transcription_errors import (
    InvalidTranscriptionEngineOutputError,
    TranscriptionEngineUnavailableError,
    TranscriptionModelInitializationError,
)
from saxo_ai.domain.transcription import TranscriptionSettings
from saxo_ai.infrastructure.hf_baseline_contract import (
    BASELINE_PACKAGE_NAME,
    BASELINE_RUNTIME_REQUIREMENTS,
    BaselineRuntime,
    RuntimeDistributionRequirement,
)

_AUDIOREAD_STDLIB_DEPRECATION = (
    r"'(?:aifc|audioop|sunau)' is deprecated and slated for removal in Python 3\.13"
)


class _ExternalTranscriptionModel(Protocol):
    def transcribe(
        self,
        audio_path: Path,
        midi_path: Path,
        *,
        activations: bool,
    ) -> object: ...


class _HfMidiRuntime:
    def __init__(self, model: object) -> None:
        self._model = cast(_ExternalTranscriptionModel, model)

    def transcribe(self, *, audio_path: Path, midi_path: Path) -> object:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=_AUDIOREAD_STDLIB_DEPRECATION,
                category=DeprecationWarning,
            )
            returned = self._model.transcribe(audio_path, midi_path, activations=True)
        if not isinstance(returned, tuple) or len(returned) != 2:
            raise InvalidTranscriptionEngineOutputError(
                "baseline runtime must return a MIDI path and activation result"
            )
        return returned[1]


_FULL_GIT_REVISION = re.compile(r"[0-9a-f]{40}\Z")


def _verify_distribution(requirement: RuntimeDistributionRequirement) -> str:
    try:
        distribution = metadata.distribution(requirement.package_name)
    except metadata.PackageNotFoundError as error:
        raise TranscriptionEngineUnavailableError(
            f"Required baseline runtime package {requirement.package_name!r} is not installed"
        ) from error

    if distribution.version != requirement.package_version:
        raise TranscriptionEngineUnavailableError(
            f"Baseline runtime package {requirement.package_name!r} has incompatible version"
        )

    try:
        raw_direct_url = distribution.read_text("direct_url.json")
        if raw_direct_url is None:
            raise ValueError("missing direct_url.json")
        direct_url = json.loads(raw_direct_url)
        vcs_info = direct_url["vcs_info"]
        source_url = direct_url["url"]
        vcs = vcs_info["vcs"]
        commit_id = vcs_info["commit_id"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise TranscriptionEngineUnavailableError(
            f"Baseline runtime source provenance is unavailable for {requirement.package_name!r}"
        ) from error

    if source_url != requirement.source_url:
        raise TranscriptionEngineUnavailableError(
            f"Baseline runtime source provenance URL is incompatible for "
            f"{requirement.package_name!r}"
        )
    if vcs != "git":
        raise TranscriptionEngineUnavailableError(
            f"Baseline runtime source provenance VCS is incompatible for "
            f"{requirement.package_name!r}"
        )
    if not isinstance(commit_id, str) or _FULL_GIT_REVISION.fullmatch(commit_id) is None:
        raise TranscriptionEngineUnavailableError(
            f"Baseline runtime source provenance revision is not a full commit for "
            f"{requirement.package_name!r}"
        )
    if commit_id != requirement.source_revision:
        raise TranscriptionEngineUnavailableError(
            f"Baseline runtime source provenance revision is incompatible for "
            f"{requirement.package_name!r}"
        )
    return distribution.version


def verify_baseline_runtime() -> dict[str, str]:
    return {
        requirement.package_name: _verify_distribution(requirement)
        for requirement in BASELINE_RUNTIME_REQUIREMENTS
    }


class HfMidiRuntimeFactory:
    def ensure_available(self) -> str:
        return verify_baseline_runtime()[BASELINE_PACKAGE_NAME]

    def create(
        self,
        *,
        checkpoint_path: Path,
        settings: TranscriptionSettings,
    ) -> BaselineRuntime:
        try:
            package = import_module("hf_midi_transcription")
            model = package.MidiTranscriptionModel(
                device=settings.device,
                instrument="saxophone",
                checkpoint_path=str(checkpoint_path),
                batch_size=8,
                onset_threshold=settings.onset_threshold,
                offset_threshold=settings.offset_threshold,
                frame_threshold=settings.frame_threshold,
            )
        except Exception as error:
            raise TranscriptionModelInitializationError(
                "Verified FiloSax checkpoint could not initialize the baseline runtime"
            ) from error
        return _HfMidiRuntime(model)
