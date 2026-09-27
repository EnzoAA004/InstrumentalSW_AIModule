package com.instrumentalsw.backend.web;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.instrumentalsw.backend.application.TranscriptionGateway;
import com.instrumentalsw.backend.configuration.UploadConfiguration;
import com.instrumentalsw.backend.domain.InputMode;
import com.instrumentalsw.backend.domain.SaxophoneType;
import com.instrumentalsw.backend.domain.TranscriptionException;
import com.instrumentalsw.backend.domain.TranscriptionJob;
import com.instrumentalsw.backend.domain.UploadErrorCode;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(TranscriptionStatusController.class)
@Import({UploadConfiguration.class, ApiExceptionHandler.class})
@ActiveProfiles("test")
class TranscriptionStatusControllerTest {
    private static final UUID JOB_ID = UUID.fromString("11111111-1111-1111-1111-111111111111");
    private static final String FRONTEND_ORIGIN = "http://localhost:3000";

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private TranscriptionGateway gateway;

    @BeforeEach
    void configureGateway() {
        when(gateway.get(JOB_ID)).thenReturn(job());
    }

    @Test
    void validGetReturns200JsonAndPreservesEveryFastApiField() throws Exception {
        mockMvc.perform(get("/api/v1/transcriptions/{jobId}", JOB_ID))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.job_id").value(JOB_ID.toString()))
                .andExpect(jsonPath("$.status").value("UPLOADED"))
                .andExpect(jsonPath("$.filename").value("take.wav"))
                .andExpect(jsonPath("$.size_bytes").value(15))
                .andExpect(jsonPath("$.audio_sha256").value("a".repeat(64)))
                .andExpect(jsonPath("$.saxophone_type").value("alto"))
                .andExpect(jsonPath("$.input_mode").value("solo"));

        verify(gateway).get(JOB_ID);
    }

    @Test
    void malformedUuidReturnsStable400WithoutCallingTheGateway() throws Exception {
        mockMvc.perform(get("/api/v1/transcriptions/not-a-uuid"))
                .andExpect(status().isBadRequest())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.code").value("INVALID_JOB_ID"))
                .andExpect(jsonPath("$.message").value("Job ID must be a valid UUID."))
                .andExpect(jsonPath("$.field").value("job_id"));
    }

    @Test
    void unknownJobReturnsStable404WithoutLeakingUpstreamDetails() throws Exception {
        when(gateway.get(JOB_ID))
                .thenThrow(new TranscriptionException(
                        UploadErrorCode.TRANSCRIPTION_NOT_FOUND, "Transcription job not found.", "job_id"));

        mockMvc.perform(get("/api/v1/transcriptions/{jobId}", JOB_ID))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("TRANSCRIPTION_NOT_FOUND"))
                .andExpect(jsonPath("$.message").value("Transcription job not found."))
                .andExpect(jsonPath("$.field").value("job_id"))
                .andExpect(content().string(not(containsString("localhost:8000"))))
                .andExpect(content().string(not(containsString("private upstream"))));
    }

    @Test
    void configuredFrontendOriginMayPreflightGetWithoutCredentials() throws Exception {
        mockMvc.perform(options("/api/v1/transcriptions/{jobId}", JOB_ID)
                        .header(HttpHeaders.ORIGIN, FRONTEND_ORIGIN)
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, HttpMethod.GET.name()))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, FRONTEND_ORIGIN))
                .andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_METHODS, containsString("GET")))
                .andExpect(header().doesNotExist(HttpHeaders.ACCESS_CONTROL_ALLOW_CREDENTIALS));
    }

    @Test
    void unconfiguredOriginIsRejected() throws Exception {
        mockMvc.perform(options("/api/v1/transcriptions/{jobId}", JOB_ID)
                        .header(HttpHeaders.ORIGIN, "https://untrusted.example")
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, HttpMethod.GET.name()))
                .andExpect(status().isForbidden())
                .andExpect(header().doesNotExist(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN));
    }

    private static TranscriptionJob job() {
        return new TranscriptionJob(
                JOB_ID, "UPLOADED", "take.wav", 15, "a".repeat(64), SaxophoneType.ALTO, InputMode.SOLO);
    }
}
