package com.instrumentalsw.backend.web;

import com.instrumentalsw.backend.application.SubmitTranscription;
import com.instrumentalsw.backend.domain.TranscriptionException;
import com.instrumentalsw.backend.domain.UploadErrorCode;
import java.io.IOException;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/v1/transcriptions")
public final class TranscriptionUploadController {
    private final SubmitTranscription submitTranscription;

    public TranscriptionUploadController(SubmitTranscription submitTranscription) {
        this.submitTranscription = submitTranscription;
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<TranscriptionJobResponse> submit(
            @RequestParam(value = "file", required = false) MultipartFile file,
            @RequestParam(value = "saxophone_type", required = false) String saxophoneType,
            @RequestParam(value = "input_mode", required = false) String inputMode) {
        try {
            String filename = file == null ? null : file.getOriginalFilename();
            String contentType = file == null ? null : file.getContentType();
            byte[] content = file == null ? null : file.getBytes();
            var job = submitTranscription.execute(filename, contentType, content, saxophoneType, inputMode);
            return ResponseEntity.status(HttpStatus.ACCEPTED).body(TranscriptionJobResponse.from(job));
        } catch (IOException error) {
            throw new TranscriptionException(
                    UploadErrorCode.INVALID_TRANSCRIPTION_REQUEST, "The audio file could not be read.", "file", error);
        }
    }
}
