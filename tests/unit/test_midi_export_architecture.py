from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_midi_artifact_hashing_stays_outside_domain() -> None:
    domain = (ROOT / "src/saxo_ai/domain/midi_export.py").read_text(encoding="utf-8")
    application = (ROOT / "src/saxo_ai/application/midi_export.py").read_text(encoding="utf-8")

    assert "hashlib" not in domain
    assert "from hashlib import sha256" in application
