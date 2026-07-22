from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from uuid import UUID

from saxo_ai.checksums import sha256_hex


class InvalidRevisionArtifactError(ValueError):
    """Raised when revision artifact metadata or bytes are inconsistent."""


class ArtifactType(StrEnum):
    MIDI = "midi"
    MUSICXML = "musicxml"
    SVG = "svg"


_ARTIFACT_METADATA: dict[ArtifactType, tuple[str, str]] = {
    ArtifactType.MIDI: ("audio/midi", ".mid"),
    ArtifactType.MUSICXML: ("application/vnd.recordare.musicxml+xml", ".musicxml"),
    ArtifactType.SVG: ("image/svg+xml", ".svg"),
}
_ARTIFACT_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def is_safe_artifact_id(value: object) -> bool:
    return isinstance(value, str) and _ARTIFACT_ID.fullmatch(value) is not None


@dataclass(frozen=True, slots=True)
class RevisionArtifactDescriptor:
    artifact_id: str
    artifact_type: ArtifactType
    filename: str
    media_type: str
    extension: str
    size_bytes: int
    sha256: str
    order: int

    def __post_init__(self) -> None:
        if not is_safe_artifact_id(self.artifact_id):
            raise InvalidRevisionArtifactError("artifact_id must be a safe stable identifier")
        if not isinstance(self.artifact_type, ArtifactType):
            raise InvalidRevisionArtifactError("artifact_type must be midi, musicxml, or svg")
        if (
            not isinstance(self.filename, str)
            or not self.filename
            or self.filename.startswith(".")
            or ".." in self.filename
            or "/" in self.filename
            or "\\" in self.filename
            or "\r" in self.filename
            or "\n" in self.filename
            or _FILENAME.fullmatch(self.filename) is None
        ):
            raise InvalidRevisionArtifactError("filename must be a safe relative basename")
        expected_media_type, expected_extension = _ARTIFACT_METADATA[self.artifact_type]
        if self.media_type != expected_media_type:
            raise InvalidRevisionArtifactError("media_type is incompatible with artifact_type")
        if self.extension != expected_extension:
            raise InvalidRevisionArtifactError("extension is incompatible with artifact_type")
        if not self.filename.endswith(self.extension):
            raise InvalidRevisionArtifactError("filename must end with the declared extension")
        if (
            isinstance(self.size_bytes, bool)
            or not isinstance(self.size_bytes, int)
            or self.size_bytes <= 0
        ):
            raise InvalidRevisionArtifactError("size_bytes must be a positive integer")
        if not isinstance(self.sha256, str) or _SHA256.fullmatch(self.sha256) is None:
            raise InvalidRevisionArtifactError("sha256 must be 64 lowercase hexadecimal characters")
        if isinstance(self.order, bool) or not isinstance(self.order, int) or self.order < 0:
            raise InvalidRevisionArtifactError("order must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class RevisionArtifact:
    descriptor: RevisionArtifactDescriptor
    content: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.descriptor, RevisionArtifactDescriptor):
            raise InvalidRevisionArtifactError("descriptor must be RevisionArtifactDescriptor")
        if not isinstance(self.content, bytes) or not self.content:
            raise InvalidRevisionArtifactError("content must be non-empty immutable bytes")
        if len(self.content) != self.descriptor.size_bytes:
            raise InvalidRevisionArtifactError("size_bytes must equal the exact content length")
        if sha256_hex(self.content) != self.descriptor.sha256:
            raise InvalidRevisionArtifactError("sha256 must match the exact content bytes")


@dataclass(frozen=True, slots=True)
class RevisionArtifactBundle:
    job_id: UUID
    revision_number: int
    artifacts: tuple[RevisionArtifact, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.job_id, UUID):
            raise InvalidRevisionArtifactError("job_id must be UUID")
        if (
            isinstance(self.revision_number, bool)
            or not isinstance(self.revision_number, int)
            or self.revision_number < 0
        ):
            raise InvalidRevisionArtifactError("revision_number must be non-negative")
        if not isinstance(self.artifacts, tuple) or not self.artifacts:
            raise InvalidRevisionArtifactError("a registered bundle must contain artifacts")
        if any(not isinstance(value, RevisionArtifact) for value in self.artifacts):
            raise InvalidRevisionArtifactError("artifacts must contain RevisionArtifact values")
        ids = [value.descriptor.artifact_id for value in self.artifacts]
        filenames = [value.descriptor.filename for value in self.artifacts]
        orders = [value.descriptor.order for value in self.artifacts]
        if len(set(ids)) != len(ids):
            raise InvalidRevisionArtifactError("artifact IDs must be unique within a revision")
        if len(set(filenames)) != len(filenames):
            raise InvalidRevisionArtifactError("filenames must be unique within a revision")
        if orders != list(range(len(self.artifacts))):
            raise InvalidRevisionArtifactError("artifact order must be deterministic from zero")
