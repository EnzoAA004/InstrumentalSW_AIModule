from fastapi.testclient import TestClient
from tests.review_helpers import JOB_ID, build_job, build_written_result

from saxo_ai.application.transcription_review import RegisterTranscriptionReview
from saxo_ai.infrastructure.repositories import (
    InMemoryTranscriptionJobRepository,
    InMemoryTranscriptionReviewRepository,
)
from saxo_ai.main import create_app


def test_review_api_returns_exact_job_linked_json_without_unknown_fields() -> None:
    jobs = InMemoryTranscriptionJobRepository()
    reviews = InMemoryTranscriptionReviewRepository()
    jobs.save(build_job())
    RegisterTranscriptionReview(jobs, reviews).execute(JOB_ID, build_written_result())

    with TestClient(create_app(job_repository=jobs, review_repository=reviews)) as client:
        response = client.get(f"/api/v1/transcriptions/{JOB_ID}/review")

    assert response.status_code == 200
    assert response.json() == {
        "job_id": str(JOB_ID),
        "schema_version": "1.0",
        "note_event_schema_version": "1.0",
        "low_confidence_policy_version": "1.0",
        "written_pitch_policy_version": "1.0",
        "saxophone_type": "alto",
        "low_confidence_threshold": 0.5,
        "confidence_interpretation": "model_signal_not_calibrated_accuracy",
        "confidence_method": "model_probability",
        "summary": {"event_count": 2, "low_confidence_count": 1},
        "events": [
            {
                "index": 0,
                "pitch_concert_midi": 60,
                "written_pitch_midi": 69,
                "onset_seconds": 0.0,
                "offset_seconds": 0.5,
                "velocity": 90,
                "confidence": 0.42,
                "is_low_confidence": True,
            },
            {
                "index": 1,
                "pitch_concert_midi": 67,
                "written_pitch_midi": 76,
                "onset_seconds": 0.25,
                "offset_seconds": 1.0,
                "velocity": 100,
                "confidence": 0.82,
                "is_low_confidence": False,
            },
        ],
    }
    assert "duration_seconds" not in response.text
    assert "note_name" not in response.text


def test_review_api_distinguishes_unknown_and_not_ready_jobs() -> None:
    jobs = InMemoryTranscriptionJobRepository()
    reviews = InMemoryTranscriptionReviewRepository()
    app = create_app(job_repository=jobs, review_repository=reviews)

    with TestClient(app) as client:
        missing = client.get(f"/api/v1/transcriptions/{JOB_ID}/review")
        jobs.save(build_job())
        not_ready = client.get(f"/api/v1/transcriptions/{JOB_ID}/review")

    assert missing.status_code == 404
    assert missing.json() == {
        "code": "TRANSCRIPTION_NOT_FOUND",
        "message": "Transcription job not found.",
        "field": "job_id",
    }
    assert not_ready.status_code == 409
    assert not_ready.json() == {
        "code": "TRANSCRIPTION_RESULT_NOT_READY",
        "message": "Transcription notes are not available yet.",
        "field": "job_id",
    }


def test_review_api_has_no_public_write_route() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/api/v1/transcriptions/{JOB_ID}/review",
            json={"events": []},
        )

    assert response.status_code == 405
