from __future__ import annotations

from hashlib import sha256
from uuid import UUID

import pytest

from saxo_ai.domain.revision_artifacts import (
    ArtifactType,
    InvalidRevisionArtifactError,
    RevisionArtifact,
    RevisionArtifactBundle,
    RevisionArtifactDescriptor,
)

JOB_ID = UUID("11111111-1111-1111-1111-111111111111")


def descriptor(
    *,
    artifact_id: str = "midi",
    artifact_type: ArtifactType = ArtifactType.MIDI,
    filename: str = "transcription-r0.mid",
    media_type: str = "audio/midi",
    extension: str = ".mid",
    content: bytes = b"MThd-synthetic",
    order: int = 0,
) -> RevisionArtifactDescriptor:
    return RevisionArtifactDescriptor(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        filename=filename,
        media_type=media_type,
        extension=extension,
        size_bytes=len(content),
        sha256=sha256(content).hexdigest(),
        order=order,
    )


def artifact(**overrides: object) -> RevisionArtifact:
    content = overrides.pop("content", b"MThd-synthetic")
    assert isinstance(content, bytes)
    return RevisionArtifact(
        descriptor=descriptor(content=content, **overrides),
        content=content,
    )


def test_valid_bundle_preserves_exact_immutable_bytes_and_deterministic_order() -> None:
    midi = artifact()
    xml = artifact(
        artifact_id="musicxml",
        artifact_type=ArtifactType.MUSICXML,
        filename="transcription-r0.musicxml",
        media_type="application/vnd.recordare.musicxml+xml",
        extension=".musicxml",
        content=b"<?xml version='1.0'?><score-partwise version='4.0'/>",
        order=1,
    )
    svg = artifact(
        artifact_id="svg-page-001",
        artifact_type=ArtifactType.SVG,
        filename="transcription-r0-page-001.svg",
        media_type="image/svg+xml",
        extension=".svg",
        content=b"<svg xmlns='http://www.w3.org/2000/svg'/>",
        order=2,
    )

    bundle = RevisionArtifactBundle(JOB_ID, 0, (midi, xml, svg))

    assert bundle.artifacts == (midi, xml, svg)
    assert bundle.artifacts[0].content is midi.content
    assert isinstance(bundle.artifacts[0].content, bytes)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("artifact_id", "../midi"),
        ("artifact_id", "midi/path"),
        ("filename", "../score.mid"),
        ("filename", "folder/score.mid"),
        ("filename", ".hidden.mid"),
        ("filename", "score\n.mid"),
    ],
)
def test_descriptor_rejects_unsafe_ids_and_filenames(field: str, value: str) -> None:
    kwargs = {field: value}
    with pytest.raises(InvalidRevisionArtifactError):
        descriptor(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"artifact_type": ArtifactType.MIDI, "media_type": "image/svg+xml"},
        {"artifact_type": ArtifactType.MIDI, "extension": ".svg"},
        {"artifact_type": ArtifactType.SVG, "filename": "page.mid", "extension": ".svg"},
        {"artifact_type": "pdf"},
    ],
)
def test_descriptor_rejects_incompatible_type_metadata(kwargs: dict[str, object]) -> None:
    with pytest.raises((InvalidRevisionArtifactError, ValueError)):
        descriptor(**kwargs)


def test_artifact_rejects_wrong_size_and_sha() -> None:
    content = b"exact"
    valid = descriptor(content=content)
    wrong_size = RevisionArtifactDescriptor(
        artifact_id=valid.artifact_id,
        artifact_type=valid.artifact_type,
        filename=valid.filename,
        media_type=valid.media_type,
        extension=valid.extension,
        size_bytes=valid.size_bytes + 1,
        sha256=valid.sha256,
        order=valid.order,
    )
    wrong_sha = RevisionArtifactDescriptor(
        artifact_id=valid.artifact_id,
        artifact_type=valid.artifact_type,
        filename=valid.filename,
        media_type=valid.media_type,
        extension=valid.extension,
        size_bytes=valid.size_bytes,
        sha256="0" * 64,
        order=valid.order,
    )

    with pytest.raises(InvalidRevisionArtifactError):
        RevisionArtifact(wrong_size, content)
    with pytest.raises(InvalidRevisionArtifactError):
        RevisionArtifact(wrong_sha, content)


def test_bundle_rejects_empty_duplicate_and_non_deterministic_artifacts() -> None:
    with pytest.raises(InvalidRevisionArtifactError):
        RevisionArtifactBundle(JOB_ID, 0, ())

    first = artifact()
    duplicate_id = artifact(filename="copy.mid", order=1)
    duplicate_filename = artifact(artifact_id="copy", order=1)
    skipped_order = artifact(artifact_id="copy", filename="copy.mid", order=2)

    with pytest.raises(InvalidRevisionArtifactError):
        RevisionArtifactBundle(JOB_ID, 0, (first, duplicate_id))
    with pytest.raises(InvalidRevisionArtifactError):
        RevisionArtifactBundle(JOB_ID, 0, (first, duplicate_filename))
    with pytest.raises(InvalidRevisionArtifactError):
        RevisionArtifactBundle(JOB_ID, 0, (first, skipped_order))
