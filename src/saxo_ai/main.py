from fastapi import FastAPI

from saxo_ai.api.routes import build_router
from saxo_ai.application.services import CreateTranscriptionJob, GetTranscriptionJob
from saxo_ai.domain.audio import AudioProcessingLimits
from saxo_ai.infrastructure.configuration import load_audio_processing_limits
from saxo_ai.infrastructure.hashing import Sha256AudioContentHasher
from saxo_ai.infrastructure.repositories import InMemoryTranscriptionJobRepository


def create_app(*, limits: AudioProcessingLimits | None = None) -> FastAPI:
    runtime_limits = limits or load_audio_processing_limits()
    repository = InMemoryTranscriptionJobRepository()
    application = FastAPI(title="InstrumentalSW AI Module", version="0.1.0")
    application.state.audio_processing_limits = runtime_limits
    application.include_router(
        build_router(
            CreateTranscriptionJob(
                repository,
                Sha256AudioContentHasher(
                    max_size_bytes=runtime_limits.max_size_bytes,
                ),
            ),
            GetTranscriptionJob(repository),
        )
    )
    return application


app = create_app()
