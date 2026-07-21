from hashlib import sha256

from saxo_ai.application.midi_export import build_midi_artifact


def test_build_midi_artifact_calculates_exact_sha256() -> None:
    content = b"MThd" + b"\x00" * 20

    artifact = build_midi_artifact(content)

    assert artifact.content is content
    assert artifact.size_bytes == len(content)
    assert artifact.sha256 == sha256(content).hexdigest()
