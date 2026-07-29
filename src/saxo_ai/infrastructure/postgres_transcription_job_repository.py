from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Engine
from sqlalchemy.dialects.postgresql import insert as postgres_insert

from saxo_ai.domain.models import (
    InputMode,
    JobFailureCode,
    JobStatus,
    SaxophoneType,
    TranscriptionJob,
)
from saxo_ai.infrastructure.postgres_schema import transcription_jobs


class PostgresTranscriptionJobRepository:
    """TranscriptionJobRepository backed by a real Postgres table, no in-memory state."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def save(self, job: TranscriptionJob) -> None:
        row = _row_from_job(job)
        statement = postgres_insert(transcription_jobs).values(**row)
        statement = statement.on_conflict_do_update(
            index_elements=[transcription_jobs.c.job_id],
            set_={key: value for key, value in row.items() if key != "job_id"},
        )
        with self._engine.begin() as connection:
            connection.execute(statement)

    def get(self, job_id: UUID) -> TranscriptionJob | None:
        statement = transcription_jobs.select().where(transcription_jobs.c.job_id == job_id)
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
        if row is None:
            return None
        return _job_from_row(row)


def _row_from_job(job: TranscriptionJob) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "filename": job.filename,
        "size_bytes": job.size_bytes,
        "audio_sha256": job.audio_sha256,
        "saxophone_type": job.saxophone_type.value,
        "input_mode": job.input_mode.value,
        "failure_code": job.failure_code.value if job.failure_code is not None else None,
    }


def _job_from_row(row: Any) -> TranscriptionJob:
    failure_code = row["failure_code"]
    return TranscriptionJob(
        job_id=row["job_id"],
        status=JobStatus(row["status"]),
        filename=row["filename"],
        size_bytes=row["size_bytes"],
        audio_sha256=row["audio_sha256"],
        saxophone_type=SaxophoneType(row["saxophone_type"]),
        input_mode=InputMode(row["input_mode"]),
        failure_code=JobFailureCode(failure_code) if failure_code is not None else None,
    )
