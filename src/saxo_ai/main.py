from fastapi import FastAPI

from saxo_ai.api.routes import build_router
from saxo_ai.application.ports import TranscriptionJobRepository, TranscriptionReviewRepository
from saxo_ai.application.services import CreateTranscriptionJob, GetTranscriptionJob
from saxo_ai.application.transcription_review import GetTranscriptionReview
from saxo_ai.domain.audio import AudioProcessingLimits
from saxo_ai.infrastructure.configuration import load_audio_processing_limits
from saxo_ai.infrastructure.hashing import Sha256AudioContentHasher
from saxo_ai.infrastructure.repositories import (
    InMemoryTranscriptionJobRepository,
    InMemoryTranscriptionReviewRepository,
)


def create_app(
    *,
    limits: AudioProcessingLimits | None = None,
    job_repository: TranscriptionJobRepository | None = None,
    review_repository: TranscriptionReviewRepository | None = None,
) -> FastAPI:
    runtime_limits = limits or load_audio_processing_limits()
    jobs = job_repository or InMemoryTranscriptionJobRepository()
    reviews = review_repository or InMemoryTranscriptionReviewRepository()
    application = FastAPI(title="InstrumentalSW AI Module", version="0.1.0")
    application.state.audio_processing_limits = runtime_limits
    application.state.transcription_job_repository = jobs
    application.state.transcription_review_repository = reviews
    application.include_router(
        build_router(
            CreateTranscriptionJob(
                jobs,
                Sha256AudioContentHasher(
                    max_size_bytes=runtime_limits.max_size_bytes,
                ),
            ),
            GetTranscriptionJob(jobs),
            GetTranscriptionReview(jobs, reviews),
        )
    )
    return application


app = create_app()
