package com.instrumentalsw.backend.web;

import com.instrumentalsw.backend.application.GetTranscription;
import com.instrumentalsw.backend.domain.TranscriptionException;
import com.instrumentalsw.backend.domain.UploadErrorCode;
import java.util.UUID;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/transcriptions")
public final class TranscriptionStatusController {
    private final GetTranscription getTranscription;

    public TranscriptionStatusController(GetTranscription getTranscription) {
        this.getTranscription = getTranscription;
    }

    @GetMapping(value = "/{jobId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<TranscriptionJobResponse> get(@PathVariable String jobId) {
        UUID parsedJobId;
        try {
            parsedJobId = UUID.fromString(jobId);
        } catch (IllegalArgumentException error) {
            throw new TranscriptionException(UploadErrorCode.INVALID_JOB_ID, "Job ID must be a valid UUID.", "job_id");
        }
        return ResponseEntity.ok(TranscriptionJobResponse.from(getTranscription.execute(parsedJobId)));
    }
}
