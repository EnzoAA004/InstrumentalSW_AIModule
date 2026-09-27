package com.instrumentalsw.backend.web;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.multipart.MaxUploadSizeExceededException;
import org.springframework.web.multipart.MultipartException;

class ApiExceptionHandlerTest {
    private final ApiExceptionHandler handler = new ApiExceptionHandler();

    @Test
    void mapsTransportSizeLimitToStable413Envelope() {
        var response = handler.handleSizeLimit(new MaxUploadSizeExceededException(100));

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.PAYLOAD_TOO_LARGE);
        assertThat(response.getBody())
                .isEqualTo(new ApiErrorResponse(
                        "AUDIO_SIZE_LIMIT_EXCEEDED", "The audio exceeds the accepted transport size limit.", "file"));
    }

    @Test
    void mapsMalformedMultipartToStable422Envelope() {
        var response = handler.handleMultipart(new MultipartException("private parser detail"));

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.UNPROCESSABLE_ENTITY);
        assertThat(response.getBody())
                .isEqualTo(new ApiErrorResponse(
                        "INVALID_TRANSCRIPTION_REQUEST", "The multipart transcription request is invalid.", null));
    }
}
