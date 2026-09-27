package com.instrumentalsw.backend.web;

import static org.assertj.core.api.Assertions.assertThat;

import com.instrumentalsw.backend.domain.TranscriptionException;
import com.instrumentalsw.backend.domain.UploadErrorCode;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;

class ExplicitUpstreamStatusTest {
    @Test
    void preservesAnExplicitUpstream400InsteadOfChangingItTo422() {
        ApiExceptionHandler handler = new ApiExceptionHandler();
        TranscriptionException error = new TranscriptionException(
                UploadErrorCode.INVALID_TRANSCRIPTION_REQUEST, "The transcription request was rejected.", null, 400);

        var response = handler.handleControlled(error);

        assertThat(error.publicStatus()).isEqualTo(400);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(response.getBody())
                .isEqualTo(new ApiErrorResponse(
                        "INVALID_TRANSCRIPTION_REQUEST", "The transcription request was rejected.", null));
    }
}
