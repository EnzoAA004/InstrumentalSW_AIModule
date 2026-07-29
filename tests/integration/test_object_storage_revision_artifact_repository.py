from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import Engine

from saxo_ai.application.errors import RevisionArtifactConflictError
from saxo_ai.domain.revision_artifacts import (
    ArtifactType,
    RevisionArtifact,
    RevisionArtifactBundle,
    RevisionArtifactDescriptor,
)
from saxo_ai.infrastructure.object_storage_configuration import ObjectStorageSettings
from saxo_ai.infrastructure.object_storage_revision_artifact_repository import (
    ObjectStorageRevisionArtifactRepository,
)
from saxo_ai.infrastructure.s3_object_storage import S3ObjectStorage

pytestmark = [pytest.mark.postgres_integration, pytest.mark.object_storage_integration]


def midi_artifact(content: bytes = b"fake-midi-bytes") -> RevisionArtifact:
    descriptor = RevisionArtifactDescriptor(
        artifact_id="midi",
        artifact_type=ArtifactType.MIDI,
        filename="transcription.mid",
        media_type="audio/midi",
        extension=".mid",
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        order=0,
    )
    return RevisionArtifact(descriptor=descriptor, content=content)


def sample_bundle(**overrides: object) -> RevisionArtifactBundle:
    defaults: dict[str, object] = {
        "job_id": uuid4(),
        "revision_number": 0,
        "artifacts": (midi_artifact(),),
    }
    defaults.update(overrides)
    return RevisionArtifactBundle(**defaults)  # type: ignore[arg-type]


def build_repository(
    postgres_engine: Engine, object_storage_settings: ObjectStorageSettings
) -> ObjectStorageRevisionArtifactRepository:
    storage = S3ObjectStorage(object_storage_settings)
    return ObjectStorageRevisionArtifactRepository(engine=postgres_engine, storage=storage)


class TestObjectStorageRevisionArtifactRepository:
    def test_save_then_get_bundle_round_trips(
        self, postgres_engine: Engine, object_storage_settings: ObjectStorageSettings
    ) -> None:
        repository = build_repository(postgres_engine, object_storage_settings)
        bundle = sample_bundle()

        repository.save(bundle)
        loaded = repository.get_bundle(bundle.job_id, bundle.revision_number)

        assert loaded == bundle

    def test_get_bundle_missing_returns_none(
        self, postgres_engine: Engine, object_storage_settings: ObjectStorageSettings
    ) -> None:
        repository = build_repository(postgres_engine, object_storage_settings)

        assert repository.get_bundle(uuid4(), 0) is None

    def test_get_artifact_returns_matching_artifact(
        self, postgres_engine: Engine, object_storage_settings: ObjectStorageSettings
    ) -> None:
        repository = build_repository(postgres_engine, object_storage_settings)
        bundle = sample_bundle()
        repository.save(bundle)

        loaded = repository.get_artifact(bundle.job_id, bundle.revision_number, "midi")

        assert loaded == bundle.artifacts[0]

    def test_get_artifact_missing_id_returns_none(
        self, postgres_engine: Engine, object_storage_settings: ObjectStorageSettings
    ) -> None:
        repository = build_repository(postgres_engine, object_storage_settings)
        bundle = sample_bundle()
        repository.save(bundle)

        assert repository.get_artifact(bundle.job_id, bundle.revision_number, "missing") is None

    def test_saving_identical_bundle_again_is_idempotent(
        self, postgres_engine: Engine, object_storage_settings: ObjectStorageSettings
    ) -> None:
        repository = build_repository(postgres_engine, object_storage_settings)
        bundle = sample_bundle()

        first = repository.save(bundle)
        second = repository.save(bundle)

        assert first == second == bundle

    def test_saving_conflicting_bundle_raises(
        self, postgres_engine: Engine, object_storage_settings: ObjectStorageSettings
    ) -> None:
        repository = build_repository(postgres_engine, object_storage_settings)
        job_id = uuid4()
        repository.save(sample_bundle(job_id=job_id, revision_number=0))

        conflicting = sample_bundle(
            job_id=job_id, revision_number=0, artifacts=(midi_artifact(b"different-bytes"),)
        )

        with pytest.raises(RevisionArtifactConflictError):
            repository.save(conflicting)
