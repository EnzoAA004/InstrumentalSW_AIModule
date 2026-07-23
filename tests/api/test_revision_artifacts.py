from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from tests.review_helpers import JOB_ID, build_job, build_written_result

from saxo_ai.application.midi_export import ExportWrittenPitchToMidi
from saxo_ai.domain.revision_artifacts import (
    ArtifactType,
    RevisionArtifact,
    RevisionArtifactBundle,
    RevisionArtifactDescriptor,
)
from saxo_ai.infrastructure.repositories import (
    InMemoryRevisionArtifactRepository,
    InMemoryTranscriptionJobRepository,
    InMemoryTranscriptionReviewRepository,
    InMemoryTranscriptionRevisionRepository,
)
from saxo_ai.main import create_app

NOW = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
MIDI_BYTES = b"MThd-exact-download"


def bundle() -> RevisionArtifactBundle:
    descriptor = RevisionArtifactDescriptor(
        artifact_id="midi",
        artifact_type=ArtifactType.MIDI,
        filename="transcription-r0.mid",
        media_type="audio/midi",
        extension=".mid",
        size_bytes=len(MIDI_BYTES),
        sha256=sha256(MIDI_BYTES).hexdigest(),
        order=0,
    )
    return RevisionArtifactBundle(
        JOB_ID,
        0,
        (RevisionArtifact(descriptor, MIDI_BYTES),),
    )


def registered_app(*, with_artifacts: bool = True) -> FastAPI:
    jobs = InMemoryTranscriptionJobRepository()
    reviews = InMemoryTranscriptionReviewRepository()
    revisions = InMemoryTranscriptionRevisionRepository()
    artifacts = InMemoryRevisionArtifactRepository()
    jobs.save(build_job())
    app = create_app(
        job_repository=jobs,
        review_repository=reviews,
        revision_repository=revisions,
        revision_artifact_repository=artifacts,
        clock=lambda: NOW,
    )
    app.state.register_transcription_review.execute(JOB_ID, build_written_result())
    if with_artifacts:
        app.state.register_revision_artifacts.execute(bundle())
    return app


def test_list_exposes_complete_descriptors_without_bytes_or_base64() -> None:
    with TestClient(registered_app()) as client:
        response = client.get(f"/api/v1/transcriptions/{JOB_ID}/revisions/0/artifacts")

    assert response.status_code == 200
    assert response.json() == {
        "job_id": str(JOB_ID),
        "revision_number": 0,
        "artifacts": [
            {
                "artifact_id": "midi",
                "artifact_type": "midi",
                "filename": "transcription-r0.mid",
                "media_type": "audio/midi",
                "extension": ".mid",
                "size_bytes": len(MIDI_BYTES),
                "sha256": sha256(MIDI_BYTES).hexdigest(),
                "order": 0,
            }
        ],
    }
    assert "content" not in response.text
    assert "base64" not in response.text.lower()


def test_download_returns_exact_bytes_and_security_headers() -> None:
    with TestClient(registered_app()) as client:
        response = client.get(f"/api/v1/transcriptions/{JOB_ID}/revisions/0/artifacts/midi")

    digest = sha256(MIDI_BYTES).hexdigest()
    assert response.status_code == 200
    assert response.content == MIDI_BYTES
    assert response.headers["content-type"] == "audio/midi"
    assert response.headers["content-disposition"] == 'attachment; filename="transcription-r0.mid"'
    assert response.headers["content-length"] == str(len(MIDI_BYTES))
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-sha256"] == digest
    assert response.headers["etag"] == f'"sha256-{digest}"'


def test_get_never_executes_exporters(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("download GET must not execute MIDI export")

    monkeypatch.setattr(ExportWrittenPitchToMidi, "execute", forbidden)
    with TestClient(registered_app()) as client:
        assert (
            client.get(f"/api/v1/transcriptions/{JOB_ID}/revisions/0/artifacts").status_code == 200
        )
        assert (
            client.get(f"/api/v1/transcriptions/{JOB_ID}/revisions/0/artifacts/midi").status_code
            == 200
        )


def test_stable_not_ready_missing_and_invalid_errors() -> None:
    with TestClient(registered_app(with_artifacts=False)) as client:
        not_ready = client.get(f"/api/v1/transcriptions/{JOB_ID}/revisions/0/artifacts")
        revision_missing = client.get(f"/api/v1/transcriptions/{JOB_ID}/revisions/99/artifacts")
        invalid = client.get("/api/v1/transcriptions/not-a-uuid/revisions/0/artifacts")
        unknown_job = client.get(
            "/api/v1/transcriptions/22222222-2222-2222-2222-222222222222/revisions/0/artifacts"
        )

    assert not_ready.status_code == 409
    assert not_ready.json() == {
        "code": "ARTIFACTS_NOT_READY",
        "message": "Revision artifacts are not available yet.",
        "field": "revision_number",
    }
    assert revision_missing.status_code == 404
    assert revision_missing.json()["code"] == "REVISION_NOT_FOUND"
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "INVALID_JOB_ID"
    assert unknown_job.status_code == 404
    assert unknown_job.json()["code"] == "TRANSCRIPTION_NOT_FOUND"


def test_unknown_artifact_is_404_and_no_public_write_route_exists() -> None:
    with TestClient(registered_app()) as client:
        missing = client.get(f"/api/v1/transcriptions/{JOB_ID}/revisions/0/artifacts/musicxml")
        write = client.post(
            f"/api/v1/transcriptions/{JOB_ID}/revisions/0/artifacts",
            json={},
        )

    assert missing.status_code == 404
    assert missing.json() == {
        "code": "ARTIFACT_NOT_FOUND",
        "message": "Revision artifact not found.",
        "field": "artifact_id",
    }
    assert write.status_code == 405
