from __future__ import annotations

from uuid import UUID

from saxo_ai.application.ports import BinaryStream, ObjectStorage

_ORIGINAL_AUDIO_PREFIX = "original-audio"
_ORIGINAL_AUDIO_MEDIA_TYPE = "application/octet-stream"


def original_audio_storage_key(job_id: UUID) -> str:
    return f"{_ORIGINAL_AUDIO_PREFIX}/{job_id}"


class ObjectStorageOriginalAudioRepository:
    """Store accepted original uploads privately under a deterministic job key."""

    def __init__(self, storage: ObjectStorage) -> None:
        self._storage = storage

    def save(self, job_id: UUID, source: BinaryStream) -> None:
        self._storage.put_stream(
            original_audio_storage_key(job_id),
            source,
            content_type=_ORIGINAL_AUDIO_MEDIA_TYPE,
        )

    def get(self, job_id: UUID) -> bytes | None:
        return self._storage.get(original_audio_storage_key(job_id))
