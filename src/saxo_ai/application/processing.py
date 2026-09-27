from __future__ import annotations

from saxo_ai.application.ports import (
    OriginalAudioRepository,
    TranscriptionJobProcessor,
    TranscriptionJobRepository,
    TranscriptionProcessingQueue,
)
from saxo_ai.domain.models import JobFailureCode


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
            self._jobs.save(job.mark_failed(JobFailureCode.SOURCE_AUDIO_MISSING))
            self._queue.ack(message)
            return True

        processing_job = job.mark_processing()
        self._jobs.save(processing_job)
        try:
            self._processor.process(processing_job, source)
        except Exception:
            if message.attempt < self._max_attempts:
                self._jobs.save(processing_job.mark_queued())
                self._queue.retry(message)
            else:
                self._jobs.save(processing_job.mark_failed(JobFailureCode.PROCESSING_FAILED))
                self._queue.ack(message)
            return True

        self._jobs.save(processing_job.mark_completed())
        self._queue.ack(message)
        return True
