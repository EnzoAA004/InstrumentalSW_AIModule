from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from saxo_ai.api.schemas import (
    HealthResponse,
    RegenerationRequestResponse,
    TranscriptionJobResponse,
    TranscriptionReviewResponse,
    TranscriptionRevisionHistoryResponse,
    TranscriptionRevisionResponse,
)
from saxo_ai.application.errors import (
    AudioSizeLimitExceededError,
    EmptyAudioFileError,
    InvalidRevisionEventError,
    InvalidRevisionOperationError,
    RevisionConflictError,
    RevisionNotFoundError,
    TranscriptionJobNotFoundError,
    TranscriptionResultNotReadyError,
    UnsupportedAudioFormatError,
)
from saxo_ai.application.services import CreateTranscriptionJob, GetTranscriptionJob
from saxo_ai.application.transcription_review import GetTranscriptionReview
from saxo_ai.application.transcription_revisions import (
    AddRevisionEvent,
    CreateTranscriptionRevision,
    DeleteRevisionEvent,
    GetTranscriptionRevision,
    GetTranscriptionRevisionHistory,
    RequestArtifactRegeneration,
    RevisionOperation,
    UpdateRevisionEvent,
)
from saxo_ai.domain.models import InputMode, SaxophoneType


def build_router(
    create_job: CreateTranscriptionJob,
    get_job: GetTranscriptionJob,
    get_review: GetTranscriptionReview,
    get_revision_history: GetTranscriptionRevisionHistory,
    get_revision: GetTranscriptionRevision,
    create_revision: CreateTranscriptionRevision,
    request_regeneration: RequestArtifactRegeneration,
) -> APIRouter:
    router = APIRouter()

    @router.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @router.post(
        "/api/v1/transcriptions",
        response_model=TranscriptionJobResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def create_transcription(
        file: Annotated[UploadFile, File()],
        saxophone_type: Annotated[SaxophoneType, Form()],
        input_mode: Annotated[InputMode, Form()],
    ) -> TranscriptionJobResponse:
        try:
            job = create_job.execute(
                filename=file.filename or "",
                content=file.file,
                saxophone_type=saxophone_type,
                input_mode=input_mode,
            )
        except UnsupportedAudioFormatError as error:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Only MP3 and WAV files are supported.",
            ) from error
        except EmptyAudioFileError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded audio file is empty.",
            ) from error
        except AudioSizeLimitExceededError as error:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail={
                    "code": "AUDIO_SIZE_LIMIT_EXCEEDED",
                    "message": (
                        f"Audio exceeds the maximum allowed size of {error.max_size_bytes} bytes."
                    ),
                    "max_size_bytes": error.max_size_bytes,
                },
            ) from error
        return TranscriptionJobResponse.model_validate(job)

    @router.get(
        "/api/v1/transcriptions/{job_id}", response_model=TranscriptionJobResponse
    )
    def get_transcription(job_id: UUID) -> TranscriptionJobResponse:
        try:
            return TranscriptionJobResponse.model_validate(get_job.execute(job_id))
        except TranscriptionJobNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transcription job not found.",
            ) from error

    @router.get(
        "/api/v1/transcriptions/{job_id}/review",
        response_model=TranscriptionReviewResponse,
    )
    def get_transcription_review(
        job_id: str,
    ) -> TranscriptionReviewResponse | JSONResponse:
        parsed_job_id = _parse_job_id(job_id)
        if isinstance(parsed_job_id, JSONResponse):
            return parsed_job_id
        try:
            return TranscriptionReviewResponse.model_validate(
                get_review.execute(parsed_job_id)
            )
        except TranscriptionJobNotFoundError:
            return _error(
                404,
                "TRANSCRIPTION_NOT_FOUND",
                "Transcription job not found.",
                "job_id",
            )
        except TranscriptionResultNotReadyError:
            return _result_not_ready()

    @router.get(
        "/api/v1/transcriptions/{job_id}/revisions",
        response_model=TranscriptionRevisionHistoryResponse,
    )
    def list_transcription_revisions(
        job_id: str,
    ) -> TranscriptionRevisionHistoryResponse | JSONResponse:
        parsed_job_id = _parse_job_id(job_id)
        if isinstance(parsed_job_id, JSONResponse):
            return parsed_job_id
        unavailable = _require_review(parsed_job_id, get_review)
        if unavailable is not None:
            return unavailable
        try:
            return TranscriptionRevisionHistoryResponse.model_validate(
                get_revision_history.execute(parsed_job_id)
            )
        except RevisionNotFoundError:
            return _result_not_ready()

    @router.get(
        "/api/v1/transcriptions/{job_id}/revisions/{revision_number}",
        response_model=TranscriptionRevisionResponse,
    )
    def get_transcription_revision(
        job_id: str, revision_number: str
    ) -> TranscriptionRevisionResponse | JSONResponse:
        parsed_job_id = _parse_job_id(job_id)
        if isinstance(parsed_job_id, JSONResponse):
            return parsed_job_id
        unavailable = _require_review(parsed_job_id, get_review)
        if unavailable is not None:
            return unavailable
        parsed_revision = _parse_revision_number(revision_number)
        if parsed_revision is None:
            return _revision_not_found()
        try:
            return TranscriptionRevisionResponse.model_validate(
                get_revision.execute(parsed_job_id, parsed_revision)
            )
        except RevisionNotFoundError:
            return _revision_not_found()

    @router.post(
        "/api/v1/transcriptions/{job_id}/revisions",
        response_model=TranscriptionRevisionResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_transcription_revision(
        job_id: str,
        payload: Annotated[object, Body()],
    ) -> TranscriptionRevisionResponse | JSONResponse:
        parsed_job_id = _parse_job_id(job_id)
        if isinstance(parsed_job_id, JSONResponse):
            return parsed_job_id
        unavailable = _require_review(parsed_job_id, get_review)
        if unavailable is not None:
            return unavailable
        try:
            base_revision_number, operations = _parse_revision_payload(payload)
            revision = create_revision.execute(
                parsed_job_id,
                base_revision_number=base_revision_number,
                operations=operations,
            )
            return TranscriptionRevisionResponse.model_validate(revision)
        except RevisionConflictError:
            return _error(
                409,
                "REVISION_CONFLICT",
                "The transcription revision has changed.",
                "base_revision_number",
            )
        except InvalidRevisionEventError as error:
            return _error(422, "INVALID_REVISION_EVENT", str(error), "operations")
        except (InvalidRevisionOperationError, RevisionNotFoundError) as error:
            return _error(
                422,
                "INVALID_REVISION_OPERATION",
                str(error) or "The revision operation is invalid.",
                "operations",
            )

    @router.post(
        "/api/v1/transcriptions/{job_id}/revisions/{revision_number}/regeneration-requests",
        response_model=RegenerationRequestResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def request_transcription_revision_regeneration(
        job_id: str, revision_number: str
    ) -> RegenerationRequestResponse | JSONResponse:
        parsed_job_id = _parse_job_id(job_id)
        if isinstance(parsed_job_id, JSONResponse):
            return parsed_job_id
        unavailable = _require_review(parsed_job_id, get_review)
        if unavailable is not None:
            return unavailable
        parsed_revision = _parse_revision_number(revision_number)
        if parsed_revision is None:
            return _revision_not_found()
        try:
            return RegenerationRequestResponse.model_validate(
                request_regeneration.execute(parsed_job_id, parsed_revision)
            )
        except RevisionNotFoundError:
            return _revision_not_found()

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


def _require_review(job_id: UUID, get_review: GetTranscriptionReview) -> JSONResponse | None:
    try:
        get_review.execute(job_id)
    except TranscriptionJobNotFoundError:
        return _error(
            404,
            "TRANSCRIPTION_NOT_FOUND",
            "Transcription job not found.",
            "job_id",
        )
    except TranscriptionResultNotReadyError:
        return _result_not_ready()
    return None


def _parse_revision_payload(payload: object) -> tuple[int, tuple[RevisionOperation, ...]]:
    if not isinstance(payload, dict) or set(payload) != {
        "base_revision_number",
        "operations",
    }:
        raise InvalidRevisionOperationError(
            "request must contain only base_revision_number and operations"
        )
    base = payload["base_revision_number"]
    if isinstance(base, bool) or not isinstance(base, int) or base < 0:
        raise InvalidRevisionOperationError(
            "base_revision_number must be a non-negative integer"
        )
    raw_operations = payload["operations"]
    if not isinstance(raw_operations, list) or not raw_operations:
        raise InvalidRevisionOperationError("at least one operation is required")
    return base, tuple(_parse_operation(operation) for operation in raw_operations)


def _parse_operation(value: object) -> RevisionOperation:
    if not isinstance(value, dict) or not isinstance(value.get("type"), str):
        raise InvalidRevisionOperationError("each operation must have a supported type")
    operation_type = value["type"]
    if operation_type == "update":
        if set(value) != {
            "type",
            "event_id",
            "written_pitch_midi",
            "onset_seconds",
            "offset_seconds",
        }:
            raise InvalidRevisionOperationError(
                "update requires exactly its editable fields"
            )
        return UpdateRevisionEvent(
            event_id=value["event_id"],  # type: ignore[arg-type]
            written_pitch_midi=value["written_pitch_midi"],  # type: ignore[arg-type]
            onset_seconds=value["onset_seconds"],  # type: ignore[arg-type]
            offset_seconds=value["offset_seconds"],  # type: ignore[arg-type]
        )
    if operation_type == "add":
        required = {"type", "written_pitch_midi", "onset_seconds", "offset_seconds"}
        allowed = {*required, "velocity"}
        if not required <= set(value) or not set(value) <= allowed:
            raise InvalidRevisionOperationError(
                "add requires pitch, onset, offset and optional velocity"
            )
        return AddRevisionEvent(
            written_pitch_midi=value["written_pitch_midi"],  # type: ignore[arg-type]
            onset_seconds=value["onset_seconds"],  # type: ignore[arg-type]
            offset_seconds=value["offset_seconds"],  # type: ignore[arg-type]
            velocity=value.get("velocity", 64),  # type: ignore[arg-type]
        )
    if operation_type == "delete":
        if set(value) != {"type", "event_id"}:
            raise InvalidRevisionOperationError("delete accepts only event_id")
        return DeleteRevisionEvent(event_id=value["event_id"])  # type: ignore[arg-type]
    raise InvalidRevisionOperationError("unsupported revision operation type")


def _result_not_ready() -> JSONResponse:
    return _error(
        409,
        "TRANSCRIPTION_RESULT_NOT_READY",
        "Transcription notes are not available yet.",
        "job_id",
    )


def _revision_not_found() -> JSONResponse:
    return _error(
        404,
        "REVISION_NOT_FOUND",
        "Transcription revision not found.",
        "revision_number",
    )


def _error(status_code: int, code: str, message: str, field: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message, "field": field},
    )
