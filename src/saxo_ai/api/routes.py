from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from saxo_ai.api.schemas import HealthResponse, TranscriptionJobResponse
from saxo_ai.application.errors import (
    EmptyAudioFileError,
    TranscriptionJobNotFoundError,
    UnsupportedAudioFormatError,
)
from saxo_ai.application.services import CreateTranscriptionJob, GetTranscriptionJob
from saxo_ai.domain.models import InputMode, SaxophoneType


def build_router(
    create_job: CreateTranscriptionJob,
    get_job: GetTranscriptionJob,
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

    return router
