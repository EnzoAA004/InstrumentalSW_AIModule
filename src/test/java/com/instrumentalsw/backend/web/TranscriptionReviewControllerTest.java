package com.instrumentalsw.backend.web;

import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.instrumentalsw.backend.application.TranscriptionReviewGateway;
import com.instrumentalsw.backend.configuration.ReviewConfiguration;
import com.instrumentalsw.backend.domain.SaxophoneType;
import com.instrumentalsw.backend.domain.TranscriptionException;
import com.instrumentalsw.backend.domain.TranscriptionReview;
import com.instrumentalsw.backend.domain.TranscriptionReviewEvent;
import com.instrumentalsw.backend.domain.TranscriptionReviewSummary;
import com.instrumentalsw.backend.domain.UploadErrorCode;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(TranscriptionReviewController.class)
@Import({ReviewConfiguration.class, ApiExceptionHandler.class})
@ActiveProfiles("test")
class TranscriptionReviewControllerTest {
    private static final UUID JOB_ID = UUID.fromString("11111111-1111-1111-1111-111111111111");

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private TranscriptionReviewGateway gateway;

    @BeforeEach
    void configure() {
        when(gateway.get(JOB_ID)).thenReturn(review());
    }

    @Test
    void returnsExact200Payload() throws Exception {
        mockMvc.perform(get("/api/v1/transcriptions/{jobId}/review", JOB_ID))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.job_id").value(JOB_ID.toString()))
                .andExpect(jsonPath("$.schema_version").value("1.0"))
                .andExpect(jsonPath("$.note_event_schema_version").value("1.0"))
                .andExpect(jsonPath("$.low_confidence_policy_version").value("1.0"))
                .andExpect(jsonPath("$.written_pitch_policy_version").value("1.0"))
                .andExpect(jsonPath("$.saxophone_type").value("alto"))
                .andExpect(jsonPath("$.summary.event_count").value(1))
                .andExpect(jsonPath("$.summary.low_confidence_count").value(1))
                .andExpect(jsonPath("$.events[0].index").value(0))
                .andExpect(jsonPath("$.events[0].written_pitch_midi").value(69))
                .andExpect(jsonPath("$.events[0].is_low_confidence").value(true));
        verify(gateway).get(JOB_ID);
    }

    @Test
    void malformedUuidAndNotReadyUseStableEnvelopes() throws Exception {
        mockMvc.perform(get("/api/v1/transcriptions/not-a-uuid/review"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INVALID_JOB_ID"));

        when(gateway.get(JOB_ID))
                .thenThrow(new TranscriptionException(
                        UploadErrorCode.TRANSCRIPTION_RESULT_NOT_READY,
                        "Transcription notes are not available yet.",
                        "job_id"));
        mockMvc.perform(get("/api/v1/transcriptions/{jobId}/review", JOB_ID))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("TRANSCRIPTION_RESULT_NOT_READY"))
                .andExpect(jsonPath("$.message").value("Transcription notes are not available yet."))
                .andExpect(jsonPath("$.field").value("job_id"));
    }

    private static TranscriptionReview review() {
        return new TranscriptionReview(
                JOB_ID,
                "1.0",
                "1.0",
                "1.0",
                "1.0",
                SaxophoneType.ALTO,
                0.5,
                "model_signal_not_calibrated_accuracy",
                "model_probability",
                new TranscriptionReviewSummary(1, 1),
                List.of(new TranscriptionReviewEvent(0, 60, 69, 0.0, 0.5, 90, 0.42, true)));
    }
}
