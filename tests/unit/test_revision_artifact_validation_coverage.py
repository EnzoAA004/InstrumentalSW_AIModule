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
CONTENT = b"exact"
SHA = sha256(CONTENT).hexdigest()


def valid_descriptor(**changes: object) -> RevisionArtifactDescriptor:
    values: dict[str, object] = {
        "artifact_id": "midi",
        "artifact_type": ArtifactType.MIDI,
        "filename": "score.mid",
        "media_type": "audio/midi",
        "extension": ".mid",
        "size_bytes": len(CONTENT),
        "sha256": SHA,
        "order": 0,
    }
    values.update(changes)
    return RevisionArtifactDescriptor(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changes",
    [
        {"filename": "score.svg"},
        {"size_bytes": True},
        {"size_bytes": 0},
        {"sha256": "A" * 64},
        {"order": True},
        {"order": -1},
    ],
)
def test_descriptor_rejects_remaining_incompatible_shapes(changes: dict[str, object]) -> None:
    with pytest.raises(InvalidRevisionArtifactError):
        valid_descriptor(**changes)


def test_artifact_rejects_wrong_descriptor_and_mutable_or_empty_content() -> None:
    with pytest.raises(InvalidRevisionArtifactError):
        RevisionArtifact("not-a-descriptor", CONTENT)  # type: ignore[arg-type]
    with pytest.raises(InvalidRevisionArtifactError):
        RevisionArtifact(valid_descriptor(), bytearray(CONTENT))  # type: ignore[arg-type]
    with pytest.raises(InvalidRevisionArtifactError):
        RevisionArtifact(valid_descriptor(), b"")


def test_bundle_rejects_wrong_job_revision_and_collection_shapes() -> None:
    artifact = RevisionArtifact(valid_descriptor(), CONTENT)
    with pytest.raises(InvalidRevisionArtifactError):
        RevisionArtifactBundle("not-a-uuid", 0, (artifact,))  # type: ignore[arg-type]
    with pytest.raises(InvalidRevisionArtifactError):
        RevisionArtifactBundle(JOB_ID, True, (artifact,))
    with pytest.raises(InvalidRevisionArtifactError):
        RevisionArtifactBundle(JOB_ID, -1, (artifact,))
    with pytest.raises(InvalidRevisionArtifactError):
        RevisionArtifactBundle(JOB_ID, 0, [artifact])  # type: ignore[arg-type]
    with pytest.raises(InvalidRevisionArtifactError):
        RevisionArtifactBundle(JOB_ID, 0, ("not-an-artifact",))  # type: ignore[arg-type]
