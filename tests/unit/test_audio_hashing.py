from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from saxo_ai.application.errors import EmptyAudioFileError, UnsupportedAudioFormatError
from saxo_ai.application.ports import AudioContentHasher, BinaryStream, TranscriptionJobRepository
from saxo_ai.application.services import CreateTranscriptionJob
from saxo_ai.domain.models import InputMode, SaxophoneType, TranscriptionJob
from saxo_ai.infrastructure.repositories import InMemoryTranscriptionJobRepository

EXPECTED_ABC_SHA256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
ROOT = Path(__file__).resolve().parents[2]
ROUTES_PATH = ROOT / "src" / "saxo_ai" / "api" / "routes.py"


class RecordingStream:
    def __init__(self, content: bytes, *, maximum_read_size: int) -> None:
        self._content = content
        self._position = 0
        self._maximum_read_size = maximum_read_size
        self.requested_sizes: list[int] = []
        self.returned_chunks: list[bytes] = []

    def read(self, size: int) -> bytes:
        if not isinstance(size, int):
            raise AssertionError("read() must receive an explicit integer size")
        if not 0 < size <= self._maximum_read_size:
            raise AssertionError(f"invalid bounded read size: {size}")

        self.requested_sizes.append(size)
        chunk = self._content[self._position : self._position + size]
        self._position += len(chunk)
        self.returned_chunks.append(chunk)
        return chunk


class ExplodingStream:
    def read(self, size: int) -> bytes:
        raise AssertionError(f"unsupported extension consumed the stream with read({size})")


class RecordingRepository:
    def __init__(self) -> None:
        self.saved: list[TranscriptionJob] = []

    def save(self, job: TranscriptionJob) -> None:
        self.saved.append(job)

    def get(self, _job_id: object) -> TranscriptionJob | None:
        return None


def build_hasher(*, chunk_size: int = 4) -> AudioContentHasher:
    from saxo_ai.infrastructure.hashing import Sha256AudioContentHasher

    return Sha256AudioContentHasher(chunk_size=chunk_size)


def build_create_job(
    repository: TranscriptionJobRepository, *, chunk_size: int = 4
) -> CreateTranscriptionJob:
    return CreateTranscriptionJob(repository, build_hasher(chunk_size=chunk_size))


def create_job(
    service: CreateTranscriptionJob,
    *,
    filename: str,
    stream: BinaryStream,
) -> TranscriptionJob:
    return service.execute(
        filename=filename,
        content=stream,
        saxophone_type=SaxophoneType.ALTO,
        input_mode=InputMode.SOLO,
    )


def test_sha256_known_vector_abc_uses_incremental_bounded_reads() -> None:
    from saxo_ai.infrastructure.hashing import Sha256AudioContentHasher

    stream = RecordingStream(b"abc", maximum_read_size=2)
    metadata = Sha256AudioContentHasher(chunk_size=2).inspect(stream)

    assert metadata.audio_sha256 == EXPECTED_ABC_SHA256
    assert metadata.size_bytes == 3
    assert stream.requested_sizes == [2, 2, 2]
    assert sum(map(len, stream.returned_chunks)) == 3


def test_identical_content_has_same_hash_independent_of_filename() -> None:
    service = build_create_job(InMemoryTranscriptionJobRepository())

    first = create_job(
        service, filename="first.wav", stream=RecordingStream(b"same", maximum_read_size=4)
    )
    second = create_job(
        service, filename="second.mp3", stream=RecordingStream(b"same", maximum_read_size=4)
    )

    assert first.audio_sha256 == second.audio_sha256
    assert first.job_id != second.job_id


def test_same_filename_with_different_content_has_different_hashes() -> None:
    service = build_create_job(InMemoryTranscriptionJobRepository())

    first = create_job(
        service, filename="take.wav", stream=RecordingStream(b"content-a", maximum_read_size=4)
    )
    second = create_job(
        service, filename="take.wav", stream=RecordingStream(b"content-b", maximum_read_size=4)
    )

    assert first.audio_sha256 != second.audio_sha256


def test_hash_is_lowercase_64_character_hexadecimal() -> None:
    service = build_create_job(InMemoryTranscriptionJobRepository())

    job = create_job(
        service, filename="take.wav", stream=RecordingStream(b"abc", maximum_read_size=4)
    )

    assert re.fullmatch(r"[0-9a-f]{64}", job.audio_sha256)


def test_size_bytes_is_sum_of_chunks_from_same_single_pass() -> None:
    stream = RecordingStream(b"0123456789", maximum_read_size=3)
    service = build_create_job(InMemoryTranscriptionJobRepository(), chunk_size=3)

    job = create_job(service, filename="take.wav", stream=stream)

    assert job.size_bytes == 10
    assert sum(map(len, stream.returned_chunks)) == job.size_bytes
    assert stream.requested_sizes == [3, 3, 3, 3, 3]


def test_empty_stream_is_rejected_without_saving_a_job() -> None:
    repository = RecordingRepository()
    service = build_create_job(repository)

    with pytest.raises(EmptyAudioFileError):
        create_job(service, filename="empty.wav", stream=RecordingStream(b"", maximum_read_size=4))

    assert repository.saved == []


def test_unsupported_extension_is_rejected_before_stream_is_consumed() -> None:
    repository = RecordingRepository()
    service = build_create_job(repository)

    with pytest.raises(UnsupportedAudioFormatError):
        create_job(service, filename="take.flac", stream=ExplodingStream())

    assert repository.saved == []


def test_post_and_get_expose_expected_audio_sha256_without_local_path(client: TestClient) -> None:
    created_response = client.post(
        "/api/v1/transcriptions",
        files={"file": ("abc.wav", b"abc", "audio/wav")},
        data={"saxophone_type": "alto", "input_mode": "solo"},
    )

    assert created_response.status_code == 202
    created = created_response.json()
    assert created["audio_sha256"] == EXPECTED_ABC_SHA256
    assert created["size_bytes"] == 3
    assert "path" not in created

    queried_response = client.get(f"/api/v1/transcriptions/{created['job_id']}")
    assert queried_response.status_code == 200
    assert queried_response.json() == created


def test_hasher_rejects_non_positive_chunk_size() -> None:
    from saxo_ai.infrastructure.hashing import Sha256AudioContentHasher

    with pytest.raises(ValueError, match="greater than zero"):
        Sha256AudioContentHasher(chunk_size=0)


def test_architecture_keeps_framework_and_hashlib_dependencies_outward() -> None:
    application_and_domain = [
        *sorted((ROOT / "src" / "saxo_ai" / "application").glob("*.py")),
        *sorted((ROOT / "src" / "saxo_ai" / "domain").glob("*.py")),
    ]

    for path in application_and_domain:
        source = path.read_text(encoding="utf-8")
        assert "fastapi" not in source
        if "domain" in path.parts:
            assert "hashlib" not in source

    hashing_source = (ROOT / "src" / "saxo_ai" / "infrastructure" / "hashing.py").read_text(
        encoding="utf-8"
    )
    assert "import hashlib" in hashing_source


def test_api_route_does_not_await_unbounded_upload_read() -> None:
    tree = ast.parse(ROUTES_PATH.read_text(encoding="utf-8"))

    async_creation_handlers: Iterator[ast.AsyncFunctionDef] = (
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "create_transcription"
    )
    awaited_reads = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Await)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "read"
    ]

    assert list(async_creation_handlers) == []
    assert awaited_reads == []
