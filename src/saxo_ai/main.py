from fastapi import FastAPI

from saxo_ai.api.routes import build_router
from saxo_ai.application.services import CreateTranscriptionJob, GetTranscriptionJob
from saxo_ai.infrastructure.repositories import InMemoryTranscriptionJobRepository


def create_app() -> FastAPI:
    repository = InMemoryTranscriptionJobRepository()
    application = FastAPI(title="InstrumentalSW AI Module", version="0.1.0")
    application.include_router(
        build_router(
            CreateTranscriptionJob(repository),
            GetTranscriptionJob(repository),
        )
    )
    return application


app = create_app()
