from __future__ import annotations

from io import BytesIO
from uuid import UUID

from fastapi.testclient import TestClient

from saxo_ai.application.ports import BinaryStream
from saxo_ai.application.services import CreateTranscriptionJob
from saxo_ai.domain.models import InputMode, SaxophoneType
from saxo_ai.infrastructure.hashing import Sha256AudioContentHasher
from saxo_ai.infrastructure.object_storage_original_audio_repository import (
    ObjectStorageOriginalAudioRepository,
)
from saxo_ai.infrastructure.repositories import InMemoryTranscriptionJobRepository
from saxo_ai.main import create_app


class FakeObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.content_types: dict[str, str] = {}

    def put(self, key: str, content: bytes, *, content_type: str) -> None:
        self.objects[key] = content
        self.content_types[key] = content_type

    def put_stream(self, key: str, source: BinaryStream, *, content_type: str) -> None:
        self.objects[key] = source.read(-1)
        self.content_types[key] = content_type

    def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    def generate_presigned_get_url(self, key: str, *, expires_in_seconds: int) -> str:
        return f"https://storage.invalid/{key}?expires={expires_in_seconds}"


class RecordingOriginalAudioRepository:
    def __init__(self) -> None:
        self.saved: dict[UUID, bytes] = {}

    def save(self, job_id: UUID, source: BinaryStream) -> None:
        self.saved[job_id] = source.read(-1)

    def get(self, job_id: UUID) -> bytes | None:
        return self.saved.get(job_id)


def test_object_storage_original_audio_repository_round_trips_private_bytes() -> None:
    storage = FakeObjectStorage()
    repository = ObjectStorageOriginalAudioRepository(storage)
    job_id = UUID("3b241101-e2bb-4255-8caf-4136c566a962")

    repository.save(job_id, BytesIO(b"original-audio"))

    assert repository.get(job_id) == b"original-audio"
    assert storage.objects == {f"original-audio/{job_id}": b"original-audio"}
    assert storage.content_types == {f"original-audio/{job_id}": "application/octet-stream"}


def test_create_job_rewinds_and_persists_original_audio_after_hashing() -> None:
    jobs = InMemoryTranscriptionJobRepository()
    originals = RecordingOriginalAudioRepository()
    use_case = CreateTranscriptionJob(
        jobs,
        Sha256AudioContentHasher(),
        original_audio_repository=originals,
    )
    content = BytesIO(b"durable-source")

    job = use_case.execute(
        filename="solo.wav",
        content=content,
        saxophone_type=SaxophoneType.ALTO,
        input_mode=InputMode.SOLO,
    )

    assert originals.saved[job.job_id] == b"durable-source"
    assert jobs.get(job.job_id) == job


def test_create_app_wires_original_audio_repository_into_upload_endpoint() -> None:
    originals = RecordingOriginalAudioRepository()

    with TestClient(create_app(original_audio_repository=originals)) as client:
        response = client.post(
            "/api/v1/transcriptions",
            files={"file": ("solo.wav", b"api-source", "audio/wav")},
            data={"saxophone_type": "alto", "input_mode": "solo"},
        )

    assert response.status_code == 202
    job_id = UUID(response.json()["job_id"])
    assert originals.saved[job_id] == b"api-source"
