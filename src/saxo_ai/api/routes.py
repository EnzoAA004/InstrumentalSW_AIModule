from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from saxo_ai.api.schemas import (
    HealthResponse,
    TranscriptionJobResponse,
    TranscriptionReviewResponse,
)
from saxo_ai.application.errors import (
    AudioSizeLimitExceededError,
    EmptyAudioFileError,
    TranscriptionJobNotFoundError,
    TranscriptionResultNotReadyError,
    UnsupportedAudioFormatError,
)
from saxo_ai.application.services import CreateTranscriptionJob, GetTranscriptionJob
from saxo_ai.application.transcription_review import GetTranscriptionReview
from saxo_ai.domain.models import InputMode, SaxophoneType


def build_router(
    create_job: CreateTranscriptionJob,
    get_job: GetTranscriptionJob,
    get_review: GetTranscriptionReview,
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
        "/api/v1/transcriptions/{job_id}",
        response_model=TranscriptionJobResponse,
    )
    def get_transcription(job_id: UUID) -> TranscriptionJobResponse:
        try:
            job = get_job.execute(job_id)
        except TranscriptionJobNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transcription job not found.",
            ) from error
        return TranscriptionJobResponse.model_validate(job)

    @router.get(
        "/api/v1/transcriptions/{job_id}/review",
        response_model=TranscriptionReviewResponse,
        responses={404: {"description": "Unknown job"}, 409: {"description": "Result not ready"}},
    )
    def get_transcription_review(
        job_id: UUID,
    ) -> TranscriptionReviewResponse | JSONResponse:
        try:
            snapshot = get_review.execute(job_id)
        except TranscriptionJobNotFoundError:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "code": "TRANSCRIPTION_NOT_FOUND",
                    "message": "Transcription job not found.",
                    "field": "job_id",
                },
            )
        except TranscriptionResultNotReadyError:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "code": "TRANSCRIPTION_RESULT_NOT_READY",
                    "message": "Transcription notes are not available yet.",
                    "field": "job_id",
                },
            )
        return TranscriptionReviewResponse.model_validate(snapshot)

    return router
