from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

from saxo_ai.application.transcription_errors import TranscriptionEngineUnavailableError
from saxo_ai.infrastructure import hf_baseline_contract as contract
from saxo_ai.infrastructure.hf_runtime import HfMidiRuntimeFactory
from saxo_ai.infrastructure.hf_saxophone import HfSaxophoneTranscriptionEngine
from tests.unit.hf_saxophone_fakes import SpyStream

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = ROOT / "pyproject.toml"
_FULL_GIT_REVISION = re.compile(r"[0-9a-f]{40}\Z")


class FakeDistribution:
    def __init__(self, *, version: str, direct_url: str | None) -> None:
        self.version = version
        self._direct_url = direct_url

    def read_text(self, filename: str) -> str | None:
        assert filename == "direct_url.json"
        return self._direct_url


class NeverInitializeRuntimeFactory(HfMidiRuntimeFactory):
    def __init__(self) -> None:
        self.create_called = False

    def create(self, **kwargs: object) -> object:
        self.create_called = True
        raise AssertionError("model initialization must not run")


def _direct_url(url: str, revision: str) -> str:
    return json.dumps(
        {
            "url": url,
            "vcs_info": {
                "vcs": "git",
                "commit_id": revision,
                "requested_revision": revision,
            },
        }
    )


def _exact_distributions() -> dict[str, FakeDistribution]:
    return {
        contract.BASELINE_PACKAGE_NAME: FakeDistribution(
            version=contract.BASELINE_PACKAGE_VERSION,
            direct_url=_direct_url(
                contract.BASELINE_SOURCE_URL,
                contract.BASELINE_SOURCE_REVISION,
            ),
        ),
        contract.PIANO_TRANSCRIPTION_PACKAGE_NAME: FakeDistribution(
            version=contract.PIANO_TRANSCRIPTION_PACKAGE_VERSION,
            direct_url=_direct_url(
                contract.PIANO_TRANSCRIPTION_SOURCE_URL,
                contract.PIANO_TRANSCRIPTION_SOURCE_REVISION,
            ),
        ),
    }


def _install_fake_distributions(
    monkeypatch: pytest.MonkeyPatch,
    distributions: dict[str, FakeDistribution],
) -> None:
    def distribution(name: str) -> FakeDistribution:
        if name not in distributions:
            raise AssertionError(f"unexpected distribution lookup: {name}")
        return distributions[name]

    monkeypatch.setattr("saxo_ai.infrastructure.hf_runtime.metadata.distribution", distribution)


def test_all_baseline_git_dependencies_use_exact_full_revisions() -> None:
    configuration = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    dependencies = configuration["project"]["optional-dependencies"]["baseline"]
    git_dependencies = [dependency for dependency in dependencies if "git+" in dependency]

    expected = {
        contract.BASELINE_PACKAGE_NAME: contract.BASELINE_SOURCE_REVISION,
        contract.PIANO_TRANSCRIPTION_PACKAGE_NAME: contract.PIANO_TRANSCRIPTION_SOURCE_REVISION,
    }
    observed: dict[str, str] = {}
    for dependency in git_dependencies:
        package_name, reference = dependency.split("@", maxsplit=1)
        revision = reference.rsplit("@", maxsplit=1)[1].split(";", maxsplit=1)[0].strip()
        normalized_name = package_name.strip()
        assert _FULL_GIT_REVISION.fullmatch(revision), dependency
        observed[normalized_name] = revision

    assert observed == expected


@pytest.mark.parametrize(
    "reference",
    [
        "git+https://github.com/owner/repository.git",
        "git+https://github.com/owner/repository.git@master",
        "git+https://github.com/owner/repository.git@main",
        "git+https://github.com/owner/repository.git@vague-tag",
    ],
)
def test_floating_git_references_are_not_full_revisions(reference: str) -> None:
    revision = reference.rsplit("@", maxsplit=1)[-1]
    assert _FULL_GIT_REVISION.fullmatch(revision) is None


def test_runtime_accepts_exact_versions_urls_and_pep610_commits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_distributions(monkeypatch, _exact_distributions())

    assert HfMidiRuntimeFactory().ensure_available() == contract.BASELINE_PACKAGE_VERSION


@pytest.mark.parametrize("package_name", ["baseline", "piano"])
def test_runtime_rejects_missing_direct_url_metadata(
    monkeypatch: pytest.MonkeyPatch,
    package_name: str,
) -> None:
    distributions = _exact_distributions()
    key = (
        contract.BASELINE_PACKAGE_NAME
        if package_name == "baseline"
        else contract.PIANO_TRANSCRIPTION_PACKAGE_NAME
    )
    distributions[key] = FakeDistribution(version=distributions[key].version, direct_url=None)
    _install_fake_distributions(monkeypatch, distributions)

    with pytest.raises(TranscriptionEngineUnavailableError, match="source provenance"):
        HfMidiRuntimeFactory().ensure_available()


def test_runtime_rejects_malformed_direct_url_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    distributions = _exact_distributions()
    distributions[contract.BASELINE_PACKAGE_NAME] = FakeDistribution(
        version=contract.BASELINE_PACKAGE_VERSION,
        direct_url="{not-json",
    )
    _install_fake_distributions(monkeypatch, distributions)

    with pytest.raises(TranscriptionEngineUnavailableError, match="source provenance"):
        HfMidiRuntimeFactory().ensure_available()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("url", "https://github.com/other/hf_midi_transcription.git"),
        ("commit_id", "0" * 40),
        ("commit_id", "main"),
    ],
)
def test_runtime_rejects_wrong_baseline_source_provenance(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
) -> None:
    payload: dict[str, Any] = json.loads(
        _direct_url(contract.BASELINE_SOURCE_URL, contract.BASELINE_SOURCE_REVISION)
    )
    if field == "url":
        payload["url"] = value
    else:
        payload["vcs_info"][field] = value
    distributions = _exact_distributions()
    distributions[contract.BASELINE_PACKAGE_NAME] = FakeDistribution(
        version=contract.BASELINE_PACKAGE_VERSION,
        direct_url=json.dumps(payload),
    )
    _install_fake_distributions(monkeypatch, distributions)

    with pytest.raises(TranscriptionEngineUnavailableError, match="source provenance"):
        HfMidiRuntimeFactory().ensure_available()


def test_runtime_rejects_wrong_transitive_source_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    distributions = _exact_distributions()
    distributions[contract.PIANO_TRANSCRIPTION_PACKAGE_NAME] = FakeDistribution(
        version=contract.PIANO_TRANSCRIPTION_PACKAGE_VERSION,
        direct_url=_direct_url(contract.PIANO_TRANSCRIPTION_SOURCE_URL, "f" * 40),
    )
    _install_fake_distributions(monkeypatch, distributions)

    with pytest.raises(TranscriptionEngineUnavailableError, match="source provenance"):
        HfMidiRuntimeFactory().ensure_available()


def test_runtime_errors_do_not_expose_distribution_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    distributions = _exact_distributions()
    secret_path = "/secret/site-packages/direct_url.json"
    distributions[contract.BASELINE_PACKAGE_NAME] = FakeDistribution(
        version=contract.BASELINE_PACKAGE_VERSION,
        direct_url=json.dumps({"url": f"file://{secret_path}", "vcs_info": {}}),
    )
    _install_fake_distributions(monkeypatch, distributions)

    with pytest.raises(TranscriptionEngineUnavailableError) as captured:
        HfMidiRuntimeFactory().ensure_available()

    assert secret_path not in str(captured.value)


def test_source_mismatch_prevents_model_initialization(monkeypatch: pytest.MonkeyPatch) -> None:
    distributions = _exact_distributions()
    distributions[contract.PIANO_TRANSCRIPTION_PACKAGE_NAME] = FakeDistribution(
        version=contract.PIANO_TRANSCRIPTION_PACKAGE_VERSION,
        direct_url=_direct_url(contract.PIANO_TRANSCRIPTION_SOURCE_URL, "main"),
    )
    _install_fake_distributions(monkeypatch, distributions)
    factory = NeverInitializeRuntimeFactory()
    engine = HfSaxophoneTranscriptionEngine(runtime_factory=factory)

    with pytest.raises(TranscriptionEngineUnavailableError, match="source provenance"):
        engine.transcribe(SpyStream(b"wav"))

    assert factory.create_called is False
