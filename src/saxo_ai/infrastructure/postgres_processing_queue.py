from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import Engine, delete, or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert

from saxo_ai.domain.processing import ProcessingQueueMessage
from saxo_ai.infrastructure.postgres_schema import transcription_processing_queue

Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class PostgresTranscriptionProcessingQueue:
    def __init__(
        self,
        engine: Engine,
        *,
        lease_seconds: int = 300,
        retry_delay_seconds: int = 0,
        clock: Clock = _utc_now,
    ) -> None:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be non-negative")
        self._engine = engine
        self._lease = timedelta(seconds=lease_seconds)
        self._retry_delay = timedelta(seconds=retry_delay_seconds)
        self._clock = clock

    def enqueue(self, job_id: UUID) -> None:
        now = self._clock()
        statement = postgres_insert(transcription_processing_queue).values(
            job_id=job_id,
            attempt_count=0,
            available_at=now,
            claimed_at=None,
            created_at=now,
        )
        statement = statement.on_conflict_do_nothing(
            index_elements=[transcription_processing_queue.c.job_id]
        )
        with self._engine.begin() as connection:
            connection.execute(statement)

    def claim(self) -> ProcessingQueueMessage | None:
        now = self._clock()
        stale_before = now - self._lease
        with self._engine.begin() as connection:
            statement = (
                select(
                    transcription_processing_queue.c.job_id,
                    transcription_processing_queue.c.attempt_count,
                )
                .where(
                    transcription_processing_queue.c.available_at <= now,
                    or_(
                        transcription_processing_queue.c.claimed_at.is_(None),
                        transcription_processing_queue.c.claimed_at <= stale_before,
                    ),
                )
                .order_by(
                    transcription_processing_queue.c.available_at,
                    transcription_processing_queue.c.job_id,
                )
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            row = connection.execute(statement).mappings().first()
            if row is None:
                return None
            attempt = int(row["attempt_count"]) + 1
            connection.execute(
                update(transcription_processing_queue)
                .where(transcription_processing_queue.c.job_id == row["job_id"])
                .values(attempt_count=attempt, claimed_at=now)
            )
        return ProcessingQueueMessage(job_id=row["job_id"], attempt=attempt)

    def ack(self, message: ProcessingQueueMessage) -> bool:
        statement = delete(transcription_processing_queue).where(
            transcription_processing_queue.c.job_id == message.job_id,
            transcription_processing_queue.c.attempt_count == message.attempt,
        )
        with self._engine.begin() as connection:
            result = connection.execute(statement)
        return result.rowcount == 1

    def retry(self, message: ProcessingQueueMessage) -> bool:
        statement = (
            update(transcription_processing_queue)
            .where(
                transcription_processing_queue.c.job_id == message.job_id,
                transcription_processing_queue.c.attempt_count == message.attempt,
            )
            .values(
                claimed_at=None,
                available_at=self._clock() + self._retry_delay,
            )
        )
        with self._engine.begin() as connection:
            result = connection.execute(statement)
        return result.rowcount == 1
