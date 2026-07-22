from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from saxo_ai.infrastructure.repositories import (
    InMemoryRegenerationRequestRepository,
    InMemoryTranscriptionJobRepository,
    InMemoryTranscriptionReviewRepository,
    InMemoryTranscriptionRevisionRepository,
)
from saxo_ai.main import create_app
from tests.review_helpers import JOB_ID, build_job, build_written_result

NOW = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
HUMAN_ID = UUID("22222222-2222-2222-2222-222222222222")
REQUEST_ID = UUID("33333333-3333-3333-3333-333333333333")


def fixed_clock() -> datetime:
    return NOW


def uuid_values():
    values = iter((HUMAN_ID, REQUEST_ID))
    return lambda: next(values)


def registered_client() -> TestClient:
    jobs = InMemoryTranscriptionJobRepository()
    reviews = InMemoryTranscriptionReviewRepository()
    revisions = InMemoryTranscriptionRevisionRepository()
    regeneration = InMemoryRegenerationRequestRepository()
    jobs.save(build_job())
    app = create_app(
        job_repository=jobs,
        review_repository=reviews,
        revision_repository=revisions,
        regeneration_request_repository=regeneration,
        clock=fixed_clock,
        uuid_factory=uuid_values(),
    )
    app.state.register_transcription_review.execute(JOB_ID, build_written_result())
    return TestClient(app)


def test_revision_history_and_detail_expose_revision_zero_with_stable_ids() -> None:
    with registered_client() as client:
        history = client.get(f"/api/v1/transcriptions/{JOB_ID}/revisions")
        detail = client.get(f"/api/v1/transcriptions/{JOB_ID}/revisions/0")

    assert history.status_code == 200
    assert history.json() == {
        "job_id": str(JOB_ID),
        "latest_revision_number": 0,
        "revision_count": 1,
        "revisions": [
            {
                "revision_number": 0,
                "parent_revision_number": None,
                "created_at": "2026-07-22T12:00:00Z",
                "event_count": 2,
                "model_event_count": 2,
                "human_event_count": 0,
                "derived_artifacts_status": "CURRENT",
            }
        ],
    }
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["job_id"] == str(JOB_ID)
    assert payload["revision_number"] == 0
    assert payload["parent_revision_number"] is None
    assert payload["saxophone_type"] == "alto"
    assert payload["derived_artifacts_status"] == "CURRENT"
    assert [event["event_id"] for event in payload["events"]] == ["source-0", "source-1"]
    assert payload["events"][0] == {
        "event_id": "source-0",
        "origin": "model",
        "source_index": 0,
        "pitch_concert_midi": 60,
        "written_pitch_midi": 69,
        "onset_seconds": 0.0,
        "offset_seconds": 0.5,
        "velocity": 90,
        "confidence": 0.42,
        "is_low_confidence": True,
    }


def test_post_revision_applies_exact_order_and_returns_complete_revision() -> None:
    body = {
        "base_revision_number": 0,
        "operations": [
            {
                "type": "update",
                "event_id": "source-0",
                "written_pitch_midi": 70,
                "onset_seconds": 0.1,
                "offset_seconds": 0.6,
            },
            {
                "type": "add",
                "written_pitch_midi": 72,
                "onset_seconds": 0.7,
                "offset_seconds": 1.0,
                "velocity": 64,
            },
            {"type": "delete", "event_id": "source-1"},
        ],
    }
    with registered_client() as client:
        response = client.post(f"/api/v1/transcriptions/{JOB_ID}/revisions", json=body)
        history = client.get(f"/api/v1/transcriptions/{JOB_ID}/revisions")

    assert response.status_code == 201
    payload = response.json()
    assert payload["revision_number"] == 1
    assert payload["parent_revision_number"] == 0
    assert payload["derived_artifacts_status"] == "STALE"
    assert [event["event_id"] for event in payload["events"]] == [
        "source-0",
        f"human-{HUMAN_ID}",
    ]
    assert payload["events"][0]["pitch_concert_midi"] == 61
    assert payload["events"][0]["confidence"] == 0.42
    assert payload["events"][1]["origin"] == "human"
    assert payload["events"][1]["source_index"] is None
    assert payload["events"][1]["confidence"] is None
    assert payload["events"][1]["is_low_confidence"] is None
    assert history.json()["latest_revision_number"] == 1
    assert history.json()["revision_count"] == 2


def test_revision_conflict_returns_stable_409_without_partial_write() -> None:
    with registered_client() as client:
        first = client.post(
            f"/api/v1/transcriptions/{JOB_ID}/revisions",
            json={
                "base_revision_number": 0,
                "operations": [
                    {
                        "type": "update",
                        "event_id": "source-0",
                        "written_pitch_midi": 70,
                        "onset_seconds": 0.1,
                        "offset_seconds": 0.6,
                    }
                ],
            },
        )
        conflict = client.post(
            f"/api/v1/transcriptions/{JOB_ID}/revisions",
            json={
                "base_revision_number": 0,
                "operations": [{"type": "delete", "event_id": "source-1"}],
            },
        )
        history = client.get(f"/api/v1/transcriptions/{JOB_ID}/revisions")

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json() == {
        "code": "REVISION_CONFLICT",
        "message": "The transcription revision has changed.",
        "field": "base_revision_number",
    }
    assert history.json()["revision_count"] == 2


def test_regeneration_request_is_202_idempotent_and_does_not_claim_artifacts() -> None:
    with registered_client() as client:
        created = client.post(
            f"/api/v1/transcriptions/{JOB_ID}/revisions",
            json={
                "base_revision_number": 0,
                "operations": [
                    {
                        "type": "update",
                        "event_id": "source-0",
                        "written_pitch_midi": 70,
                        "onset_seconds": 0.1,
                        "offset_seconds": 0.6,
                    }
                ],
            },
        )
        first = client.post(
            f"/api/v1/transcriptions/{JOB_ID}/revisions/1/regeneration-requests"
        )
        second = client.post(
            f"/api/v1/transcriptions/{JOB_ID}/revisions/1/regeneration-requests"
        )
        detail = client.get(f"/api/v1/transcriptions/{JOB_ID}/revisions/1")

    assert created.status_code == 201
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json() == second.json()
    assert first.json() == {
        "request_id": str(HUMAN_ID),
        "job_id": str(JOB_ID),
        "revision_number": 1,
        "status": "REQUESTED",
        "requested_artifacts": ["midi", "musicxml", "svg"],
    }
    text = first.text.lower()
    assert "bytes" not in text
    assert "completed" not in text
    assert detail.json()["derived_artifacts_status"] == "REGENERATION_REQUESTED"


def test_revision_api_returns_stable_not_found_not_ready_and_invalid_errors() -> None:
    jobs = InMemoryTranscriptionJobRepository()
    app = create_app(job_repository=jobs)
    with TestClient(app) as client:
        invalid = client.get("/api/v1/transcriptions/not-a-uuid/revisions")
        missing = client.get(f"/api/v1/transcriptions/{JOB_ID}/revisions")
        jobs.save(build_job())
        not_ready = client.get(f"/api/v1/transcriptions/{JOB_ID}/revisions")
        revision_missing = client.get(f"/api/v1/transcriptions/{JOB_ID}/revisions/99")

    assert invalid.status_code == 400
    assert invalid.json()["code"] == "INVALID_JOB_ID"
    assert missing.status_code == 404
    assert missing.json()["code"] == "TRANSCRIPTION_NOT_FOUND"
    assert not_ready.status_code == 409
    assert not_ready.json()["code"] == "TRANSCRIPTION_RESULT_NOT_READY"
    assert revision_missing.status_code == 409
    assert revision_missing.json()["code"] == "TRANSCRIPTION_RESULT_NOT_READY"


def test_invalid_operations_use_stable_envelopes_and_unknown_fields_are_rejected() -> None:
    invalid_bodies = (
        {"base_revision_number": 0, "operations": []},
        {
            "base_revision_number": 0,
            "operations": [{"type": "delete", "event_id": "missing"}],
        },
        {
            "base_revision_number": 0,
            "operations": [
                {
                    "type": "update",
                    "event_id": "source-0",
                    "written_pitch_midi": 200,
                    "onset_seconds": 0.0,
                    "offset_seconds": 0.5,
                }
            ],
        },
        {
            "base_revision_number": 0,
            "operations": [
                {
                    "type": "add",
                    "written_pitch_midi": 72,
                    "onset_seconds": 0.7,
                    "offset_seconds": 1.0,
                    "confidence": 0.9,
                }
            ],
        },
        {
            "base_revision_number": 0,
            "operations": [{"type": "delete", "event_id": "source-0", "velocity": 64}],
        },
    )
    with registered_client() as client:
        responses = [
            client.post(f"/api/v1/transcriptions/{JOB_ID}/revisions", json=body)
            for body in invalid_bodies
        ]
        history = client.get(f"/api/v1/transcriptions/{JOB_ID}/revisions")

    assert all(response.status_code == 422 for response in responses)
    assert {response.json()["code"] for response in responses} <= {
        "INVALID_REVISION_OPERATION",
        "INVALID_REVISION_EVENT",
    }
    assert history.json()["revision_count"] == 1


def test_historical_revisions_cannot_be_mutated_or_deleted_through_http() -> None:
    with registered_client() as client:
        assert client.put(f"/api/v1/transcriptions/{JOB_ID}/revisions/0", json={}).status_code == 405
        assert client.patch(f"/api/v1/transcriptions/{JOB_ID}/revisions/0", json={}).status_code == 405
        assert client.delete(f"/api/v1/transcriptions/{JOB_ID}/revisions/0").status_code == 405
        assert client.post(f"/api/v1/transcriptions/{JOB_ID}/review", json={}).status_code == 405
