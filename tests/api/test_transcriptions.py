from typing import Any, Protocol
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient


class ResponseLike(Protocol):
    @property
    def status_code(self) -> int: ...

    def json(self) -> Any: ...


@pytest.mark.parametrize("filename", ["take.wav", "take.WAV", "take.mp3", "take.MP3"])
def test_create_transcription_accepts_supported_audio_extensions(
    client: TestClient, filename: str
) -> None:
    response = create_transcription(client, filename=filename, content=b"synthetic-audio")
    assert response.status_code == 202
    payload = response.json()
    UUID(payload["job_id"])
    assert payload == {
        "job_id": payload["job_id"],
        "status": "UPLOADED",
        "filename": filename,
        "size_bytes": len(b"synthetic-audio"),
        "audio_sha256": "ef746a1a59afecba50d3ce36e3506ee52784236e91034569ccb54f73fbc3c632",
        "saxophone_type": "alto",
        "input_mode": "solo",
    }
    assert "path" not in payload


def test_create_transcription_rejects_unsupported_extension(client: TestClient) -> None:
    response = create_transcription(client, filename="take.flac", content=b"synthetic-audio")
    assert response.status_code == 415
    assert response.json() == {"detail": "Only MP3 and WAV files are supported."}


def test_create_transcription_rejects_empty_file(client: TestClient) -> None:
    response = create_transcription(client, filename="empty.wav", content=b"")
    assert response.status_code == 400
    assert response.json() == {"detail": "The uploaded audio file is empty."}


def test_create_transcription_rejects_invalid_saxophone_type(client: TestClient) -> None:
    assert (
        create_transcription(
            client, filename="take.wav", content=b"synthetic-audio", saxophone_type="clarinet"
        ).status_code
        == 422
    )


def test_create_transcription_rejects_invalid_input_mode(client: TestClient) -> None:
    assert (
        create_transcription(
            client, filename="take.wav", content=b"synthetic-audio", input_mode="stream"
        ).status_code
        == 422
    )


def test_create_transcription_preserves_selected_saxophone(client: TestClient) -> None:
    assert (
        create_transcription(
            client, filename="take.wav", content=b"synthetic-audio", saxophone_type="tenor"
        ).json()["saxophone_type"]
        == "tenor"
    )


def test_create_transcription_preserves_selected_input_mode(client: TestClient) -> None:
    assert (
        create_transcription(
            client, filename="take.wav", content=b"synthetic-audio", input_mode="mixture"
        ).json()["input_mode"]
        == "mixture"
    )


def test_get_transcription_returns_created_job(client: TestClient) -> None:
    created = create_transcription(client, filename="phrase.wav", content=b"12345").json()
    response = client.get(f"/api/v1/transcriptions/{created['job_id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_get_transcription_returns_not_found_for_unknown_job(client: TestClient) -> None:
    response = client.get(f"/api/v1/transcriptions/{uuid4()}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Transcription job not found."}


def create_transcription(
    client: TestClient,
    *,
    filename: str,
    content: bytes,
    saxophone_type: str = "alto",
    input_mode: str = "solo",
) -> ResponseLike:
    return client.post(
        "/api/v1/transcriptions",
        files={"file": (filename, content, "application/octet-stream")},
        data={"saxophone_type": saxophone_type, "input_mode": input_mode},
    )
