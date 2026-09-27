package com.instrumentalsw.backend.web;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.instrumentalsw.backend.domain.TranscriptionJob;
import java.util.UUID;

public record TranscriptionJobResponse(
        @JsonProperty("job_id") UUID jobId,
        String status,
        String filename,
        @JsonProperty("size_bytes") long sizeBytes,
        @JsonProperty("audio_sha256") String audioSha256,
        @JsonProperty("saxophone_type") String saxophoneType,
        @JsonProperty("input_mode") String inputMode) {
    static TranscriptionJobResponse from(TranscriptionJob job) {
        return new TranscriptionJobResponse(
                job.jobId(),
                job.status(),
                job.filename(),
                job.sizeBytes(),
                job.audioSha256(),
                job.saxophoneType().value(),
                job.inputMode().value());
    }
}
