from __future__ import annotations

from saxo_ai.application.ports import (
    OriginalAudioRepository,
    TranscriptionJobProcessor,
    TranscriptionJobRepository,
    TranscriptionProcessingQueue,
)
from saxo_ai.domain.models import JobFailureCode


class TerminalProcessingError(RuntimeError):
    """A deterministic processor failure that must not be retried."""

    def __init__(self, failure_code: JobFailureCode) -> None:
        if not isinstance(failure_code, JobFailureCode):
            raise TypeError("failure_code must be JobFailureCode")
        super().__init__(f"terminal transcription processing failure: {failure_code.value}")
        self.failure_code = failure_code


class TranscriptionWorker:
    def __init__(
        self,
        *,
        jobs: TranscriptionJobRepository,
        originals: OriginalAudioRepository,
        queue: TranscriptionProcessingQueue,
        processor: TranscriptionJobProcessor,
        max_attempts: int = 3,
    ) -> None:
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")
        self._jobs = jobs
        self._originals = originals
        self._queue = queue
        self._processor = processor
        self._max_attempts = max_attempts

    def run_once(self) -> bool:
        message = self._queue.claim()
        if message is None:
            return False

        job = self._jobs.get(message.job_id)
        if job is None:
            self._queue.ack(message)
            return True

        source = self._originals.get(message.job_id)
        if source is None:
            if self._queue.ack(message):
                self._jobs.save(job.mark_failed(JobFailureCode.SOURCE_AUDIO_MISSING))
            return True

        processing_job = job.mark_processing()
        self._jobs.save(processing_job)
        try:
            self._processor.process(processing_job, source)
        except TerminalProcessingError as error:
            if self._queue.ack(message):
                self._jobs.save(processing_job.mark_failed(error.failure_code))
            return True
        except Exception:
            if message.attempt < self._max_attempts:
                if self._queue.retry(message):
                    self._jobs.save(processing_job.mark_queued())
            elif self._queue.ack(message):
                self._jobs.save(processing_job.mark_failed(JobFailureCode.PROCESSING_FAILED))
            return True

        if self._queue.ack(message):
            self._jobs.save(processing_job.mark_completed())
        return True
