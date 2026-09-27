from __future__ import annotations

from uuid import UUID

from sqlalchemy import Engine, RowMapping

from saxo_ai.application.errors import RevisionArtifactConflictError
from saxo_ai.application.ports import ObjectStorage
from saxo_ai.domain.revision_artifacts import (
    ArtifactType,
    RevisionArtifact,
    RevisionArtifactBundle,
    RevisionArtifactDescriptor,
)
from saxo_ai.infrastructure.postgres_schema import revision_artifact_bundles, revision_artifacts


def _storage_key(job_id: UUID, revision_number: int, descriptor: RevisionArtifactDescriptor) -> str:
    artifact_id = descriptor.artifact_id
    extension = descriptor.extension
    return f"revision-artifacts/{job_id}/{revision_number}/{artifact_id}{extension}"


class ObjectStorageRevisionArtifactRepository:
    """RevisionArtifactRepository with bytes in object storage, metadata in Postgres."""

    def __init__(self, *, engine: Engine, storage: ObjectStorage) -> None:
        self._engine = engine
        self._storage = storage

    def save(self, bundle: RevisionArtifactBundle) -> RevisionArtifactBundle:
        existing = self.get_bundle(bundle.job_id, bundle.revision_number)
        if existing is not None:
            if existing == bundle:
                return existing
            raise RevisionArtifactConflictError

        for artifact in bundle.artifacts:
            key = _storage_key(bundle.job_id, bundle.revision_number, artifact.descriptor)
            self._storage.put(key, artifact.content, content_type=artifact.descriptor.media_type)

        with self._engine.begin() as connection:
            connection.execute(
                revision_artifact_bundles.insert().values(
                    job_id=bundle.job_id, revision_number=bundle.revision_number
                )
            )
            connection.execute(
                revision_artifacts.insert(),
                [
                    _artifact_row(bundle.job_id, bundle.revision_number, artifact)
                    for artifact in bundle.artifacts
                ],
            )
        return bundle

    def get_bundle(self, job_id: UUID, revision_number: int) -> RevisionArtifactBundle | None:
        statement = (
            revision_artifacts.select()
            .where(revision_artifacts.c.job_id == job_id)
            .where(revision_artifacts.c.revision_number == revision_number)
            .order_by(revision_artifacts.c.order_index)
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        if not rows:
            return None
        artifacts = tuple(self._artifact_from_row(row) for row in rows)
        return RevisionArtifactBundle(
            job_id=job_id, revision_number=revision_number, artifacts=artifacts
        )

    def get_artifact(
        self, job_id: UUID, revision_number: int, artifact_id: str
    ) -> RevisionArtifact | None:
        statement = (
            revision_artifacts.select()
            .where(revision_artifacts.c.job_id == job_id)
            .where(revision_artifacts.c.revision_number == revision_number)
            .where(revision_artifacts.c.artifact_id == artifact_id)
        )
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
        if row is None:
            return None
        return self._artifact_from_row(row)

    def _artifact_from_row(self, row: RowMapping) -> RevisionArtifact:
        descriptor = RevisionArtifactDescriptor(
            artifact_id=row["artifact_id"],
            artifact_type=ArtifactType(row["artifact_type"]),
            filename=row["filename"],
            media_type=row["media_type"],
            extension=row["extension"],
            size_bytes=row["size_bytes"],
            sha256=row["sha256"],
            order=row["order_index"],
        )
        key = _storage_key(row["job_id"], row["revision_number"], descriptor)
        content = self._storage.get(key)
        if content is None:
            raise RuntimeError(f"object storage is missing bytes for key {key}")
        return RevisionArtifact(descriptor=descriptor, content=content)


def _artifact_row(
    job_id: UUID, revision_number: int, artifact: RevisionArtifact
) -> dict[str, object]:
    descriptor = artifact.descriptor
    return {
        "job_id": job_id,
        "revision_number": revision_number,
        "artifact_id": descriptor.artifact_id,
        "artifact_type": descriptor.artifact_type.value,
        "filename": descriptor.filename,
        "media_type": descriptor.media_type,
        "extension": descriptor.extension,
        "size_bytes": descriptor.size_bytes,
        "sha256": descriptor.sha256,
        "order_index": descriptor.order,
        "storage_key": _storage_key(job_id, revision_number, descriptor),
    }
