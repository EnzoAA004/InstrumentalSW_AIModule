from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from saxo_ai.api.schemas import RevisionArtifactListResponse
from saxo_ai.application.errors import (
    RevisionArtifactNotFoundError,
    RevisionArtifactsNotReadyError,
    RevisionNotFoundError,
    TranscriptionJobNotFoundError,
)
from saxo_ai.application.revision_artifacts import GetRevisionArtifact, ListRevisionArtifacts


def build_artifact_router(
    list_artifacts: ListRevisionArtifacts,
    get_artifact: GetRevisionArtifact,
) -> APIRouter:
    router = APIRouter()

    @router.get(
        "/api/v1/transcriptions/{job_id}/revisions/{revision_number}/artifacts",
        response_model=RevisionArtifactListResponse,
    )
    def list_revision_artifacts(
        job_id: str, revision_number: str
    ) -> RevisionArtifactListResponse | JSONResponse:
        parsed_job_id = _parse_job_id(job_id)
        if isinstance(parsed_job_id, JSONResponse):
            return parsed_job_id
        parsed_revision = _parse_revision_number(revision_number)
        if parsed_revision is None:
            return _revision_not_found()
        try:
            return RevisionArtifactListResponse.model_validate(
                list_artifacts.execute(parsed_job_id, parsed_revision)
            )
        except TranscriptionJobNotFoundError:
            return _error(
                404,
                "TRANSCRIPTION_NOT_FOUND",
                "Transcription job not found.",
                "job_id",
            )
        except RevisionNotFoundError:
            return _revision_not_found()
        except RevisionArtifactsNotReadyError:
            return _artifacts_not_ready()

    @router.get(
        "/api/v1/transcriptions/{job_id}/revisions/{revision_number}/artifacts/{artifact_id}"
    )
    def download_revision_artifact(job_id: str, revision_number: str, artifact_id: str) -> Response:
        parsed_job_id = _parse_job_id(job_id)
        if isinstance(parsed_job_id, JSONResponse):
            return parsed_job_id
        parsed_revision = _parse_revision_number(revision_number)
        if parsed_revision is None:
            return _revision_not_found()
        try:
            artifact = get_artifact.execute(parsed_job_id, parsed_revision, artifact_id)
        except TranscriptionJobNotFoundError:
            return _error(
                404,
                "TRANSCRIPTION_NOT_FOUND",
                "Transcription job not found.",
                "job_id",
            )
        except RevisionNotFoundError:
            return _revision_not_found()
        except RevisionArtifactsNotReadyError:
            return _artifacts_not_ready()
        except RevisionArtifactNotFoundError:
            return _error(
                404,
                "ARTIFACT_NOT_FOUND",
                "Revision artifact not found.",
                "artifact_id",
            )
        descriptor = artifact.descriptor
        digest = descriptor.sha256
        return Response(
            content=artifact.content,
            media_type=descriptor.media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{descriptor.filename}"',
                "Content-Length": str(descriptor.size_bytes),
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, no-store",
                "X-Content-SHA256": digest,
                "ETag": f'"sha256-{digest}"',
            },
        )

    return router


def _parse_job_id(job_id: str) -> UUID | JSONResponse:
    try:
        return UUID(job_id)
    except ValueError:
        return _error(400, "INVALID_JOB_ID", "Job ID must be a valid UUID.", "job_id")


def _parse_revision_number(value: str) -> int | None:
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 and str(parsed) == value else None


def _revision_not_found() -> JSONResponse:
    return _error(
        404,
        "REVISION_NOT_FOUND",
        "Transcription revision not found.",
        "revision_number",
    )


def _artifacts_not_ready() -> JSONResponse:
    return _error(
        409,
        "ARTIFACTS_NOT_READY",
        "Revision artifacts are not available yet.",
        "revision_number",
    )


def _error(status_code: int, code: str, message: str, field: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message, "field": field},
    )
