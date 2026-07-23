from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI

from saxo_ai.api.artifact_routes import build_artifact_router
from saxo_ai.api.routes import build_router
from saxo_ai.application.ports import (
    RegenerationRequestRepository,
    RevisionArtifactRepository,
    TranscriptionJobRepository,
    TranscriptionReviewRegistrationRepository,
    TranscriptionReviewRepository,
    TranscriptionRevisionRepository,
)
from saxo_ai.application.revision_artifacts import (
    GetRevisionArtifact,
    ListRevisionArtifacts,
    RegisterRevisionArtifacts,
)
from saxo_ai.application.services import CreateTranscriptionJob, GetTranscriptionJob
from saxo_ai.application.transcription_review import (
    GetTranscriptionReview,
    RegisterTranscriptionReview,
)
from saxo_ai.application.transcription_revisions import (
    Clock,
    CreateTranscriptionRevision,
    GetTranscriptionRevision,
    GetTranscriptionRevisionHistory,
    RequestArtifactRegeneration,
    UuidFactory,
)
from saxo_ai.domain.audio import AudioProcessingLimits
from saxo_ai.infrastructure.configuration import load_audio_processing_limits
from saxo_ai.infrastructure.hashing import Sha256AudioContentHasher
from saxo_ai.infrastructure.repositories import (
    InMemoryRegenerationRequestRepository,
    InMemoryRevisionArtifactRepository,
    InMemoryTranscriptionJobRepository,
    InMemoryTranscriptionReviewRegistrationRepository,
    InMemoryTranscriptionReviewRepository,
    InMemoryTranscriptionRevisionRepository,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def create_app(
    *,
    limits: AudioProcessingLimits | None = None,
    job_repository: TranscriptionJobRepository | None = None,
    review_repository: TranscriptionReviewRepository | None = None,
    revision_repository: TranscriptionRevisionRepository | None = None,
    review_registration_repository: TranscriptionReviewRegistrationRepository | None = None,
    regeneration_request_repository: RegenerationRequestRepository | None = None,
    revision_artifact_repository: RevisionArtifactRepository | None = None,
    clock: Clock = _utc_now,
    uuid_factory: UuidFactory = uuid4,
) -> FastAPI:
    runtime_limits = limits or load_audio_processing_limits()
    jobs = job_repository or InMemoryTranscriptionJobRepository()
    reviews = review_repository or InMemoryTranscriptionReviewRepository()
    revisions = revision_repository or InMemoryTranscriptionRevisionRepository()
    registrations = review_registration_repository or _registration_repository(
        reviews,
        revisions,
    )
    regeneration_requests = (
        regeneration_request_repository or InMemoryRegenerationRequestRepository()
    )
    revision_artifacts = revision_artifact_repository or InMemoryRevisionArtifactRepository()
    register_review = RegisterTranscriptionReview(jobs, registrations, clock)
    get_review = GetTranscriptionReview(jobs, reviews)
    register_artifacts = RegisterRevisionArtifacts(jobs, revisions, revision_artifacts)
    list_artifacts = ListRevisionArtifacts(jobs, revisions, revision_artifacts)
    get_artifact = GetRevisionArtifact(jobs, revisions, revision_artifacts)
    application = FastAPI(title="InstrumentalSW AI Module", version="0.1.0")
    application.state.audio_processing_limits = runtime_limits
    application.state.transcription_job_repository = jobs
    application.state.transcription_review_repository = reviews
    application.state.transcription_revision_repository = revisions
    application.state.transcription_review_registration_repository = registrations
    application.state.regeneration_request_repository = regeneration_requests
    application.state.revision_artifact_repository = revision_artifacts
    application.state.register_transcription_review = register_review
    application.state.register_revision_artifacts = register_artifacts
    application.include_router(
        build_router(
            CreateTranscriptionJob(
                jobs,
                Sha256AudioContentHasher(
                    max_size_bytes=runtime_limits.max_size_bytes,
                ),
            ),
            GetTranscriptionJob(jobs),
            get_review,
            GetTranscriptionRevisionHistory(revisions, regeneration_requests),
            GetTranscriptionRevision(revisions, regeneration_requests),
            CreateTranscriptionRevision(revisions, clock, uuid_factory),
            RequestArtifactRegeneration(
                revisions,
                regeneration_requests,
                clock,
                uuid_factory,
            ),
        )
    )
    application.include_router(build_artifact_router(list_artifacts, get_artifact))
    return application


def _registration_repository(
    reviews: TranscriptionReviewRepository,
    revisions: TranscriptionRevisionRepository,
) -> TranscriptionReviewRegistrationRepository:
    if not isinstance(reviews, InMemoryTranscriptionReviewRepository) or not isinstance(
        revisions, InMemoryTranscriptionRevisionRepository
    ):
        raise ValueError(
            "custom review or revision repositories require a matching registration repository"
        )
    return InMemoryTranscriptionReviewRegistrationRepository(reviews, revisions)


app = create_app()
