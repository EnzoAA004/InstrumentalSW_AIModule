from __future__ import annotations

from collections.abc import Callable
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


def artifact(
    *,
    artifact_id: str = "midi",
    artifact_type: ArtifactType = ArtifactType.MIDI,
    filename: str = "transcription-r0.mid",
    media_type: str = "audio/midi",
    extension: str = ".mid",
    content: bytes = b"MThd-synthetic",
    order: int = 0,
) -> RevisionArtifact:
    return RevisionArtifact(
        descriptor=descriptor(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            filename=filename,
            media_type=media_type,
            extension=extension,
            content=content,
            order=order,
        ),
        content=content,
    )


def descriptor_with_artifact_id(value: str) -> RevisionArtifactDescriptor:
    return descriptor(artifact_id=value)


def descriptor_with_filename(value: str) -> RevisionArtifactDescriptor:
    return descriptor(filename=value)


def descriptor_with_midi_svg_media_type() -> RevisionArtifactDescriptor:
    return descriptor(artifact_type=ArtifactType.MIDI, media_type="image/svg+xml")


def descriptor_with_midi_svg_extension() -> RevisionArtifactDescriptor:
    return descriptor(artifact_type=ArtifactType.MIDI, extension=".svg")


def descriptor_with_svg_midi_filename() -> RevisionArtifactDescriptor:
    return descriptor(
        artifact_type=ArtifactType.SVG,
        filename="page.mid",
        media_type="image/svg+xml",
        extension=".svg",
    )


def descriptor_with_unsupported_pdf_type() -> RevisionArtifactDescriptor:
    # Deliberately violates the static contract to exercise the runtime type guard.
    return descriptor(artifact_type="pdf")  # type: ignore[arg-type]


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
    ("factory", "value"),
    [
        (descriptor_with_artifact_id, "../midi"),
        (descriptor_with_artifact_id, "midi/path"),
        (descriptor_with_filename, "../score.mid"),
        (descriptor_with_filename, "folder/score.mid"),
        (descriptor_with_filename, ".hidden.mid"),
        (descriptor_with_filename, "score\n.mid"),
    ],
)
def test_descriptor_rejects_unsafe_ids_and_filenames(
    factory: Callable[[str], RevisionArtifactDescriptor], value: str
) -> None:
    with pytest.raises(InvalidRevisionArtifactError):
        factory(value)


@pytest.mark.parametrize(
    "factory",
    [
        descriptor_with_midi_svg_media_type,
        descriptor_with_midi_svg_extension,
        descriptor_with_svg_midi_filename,
        descriptor_with_unsupported_pdf_type,
    ],
)
def test_descriptor_rejects_incompatible_type_metadata(
    factory: Callable[[], RevisionArtifactDescriptor],
) -> None:
    with pytest.raises((InvalidRevisionArtifactError, ValueError)):
        factory()


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
