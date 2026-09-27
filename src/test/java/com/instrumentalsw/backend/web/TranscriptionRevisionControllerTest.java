package com.instrumentalsw.backend.web;

import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.instrumentalsw.backend.application.RevisionCreateCommand;
import com.instrumentalsw.backend.application.RevisionUpdateOperation;
import com.instrumentalsw.backend.application.TranscriptionGateway;
import com.instrumentalsw.backend.application.TranscriptionRevisionGateway;
import com.instrumentalsw.backend.configuration.RevisionConfiguration;
import com.instrumentalsw.backend.configuration.UploadConfiguration;
import com.instrumentalsw.backend.domain.TranscriptionException;
import com.instrumentalsw.backend.domain.UploadErrorCode;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(
        controllers = TranscriptionRevisionController.class,
        properties = "saxo.frontend.origin=http://localhost:3000")
@Import({RevisionConfiguration.class, UploadConfiguration.class, ApiExceptionHandler.class})
@ActiveProfiles("test")
class TranscriptionRevisionControllerTest {
    private static final UUID JOB_ID = UUID.fromString("11111111-1111-1111-1111-111111111111");

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private TranscriptionRevisionGateway gateway;

    @MockitoBean
    private TranscriptionGateway uploadGateway;

    @BeforeEach
    void configure() {
        when(gateway.history(JOB_ID)).thenReturn(TranscriptionRevisionUseCasesFixture.history());
        when(gateway.get(JOB_ID, 1)).thenReturn(TranscriptionRevisionUseCasesFixture.revision());
        when(gateway.create(eq(JOB_ID), eq(command()))).thenReturn(TranscriptionRevisionUseCasesFixture.revision());
        when(gateway.requestRegeneration(JOB_ID, 1)).thenReturn(TranscriptionRevisionUseCasesFixture.request());
    }

    @Test
    void exposesHistoryAndDetailWithCompleteFields() throws Exception {
        mockMvc.perform(get("/api/v1/transcriptions/{jobId}/revisions", JOB_ID))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.job_id").value(JOB_ID.toString()))
                .andExpect(jsonPath("$.latest_revision_number").value(1))
                .andExpect(jsonPath("$.revision_count").value(2))
                .andExpect(jsonPath("$.revisions[1].derived_artifacts_status").value("STALE"));

        mockMvc.perform(get("/api/v1/transcriptions/{jobId}/revisions/1", JOB_ID))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.revision_number").value(1))
                .andExpect(jsonPath("$.events[0].event_id").value("source-0"))
                .andExpect(jsonPath("$.events[1].origin").value("human"))
                .andExpect(jsonPath("$.events[1].confidence").doesNotExist());
        verify(gateway).history(JOB_ID);
        verify(gateway).get(JOB_ID, 1);
    }

    @Test
    void forwardsRevisionBodyAndReturns201() throws Exception {
        mockMvc.perform(
                        post("/api/v1/transcriptions/{jobId}/revisions", JOB_ID)
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(
                                        """
                                {
                                  "base_revision_number":0,
                                  "operations":[
                                    {
                                      "type":"update",
                                      "event_id":"source-0",
                                      "written_pitch_midi":70,
                                      "onset_seconds":0.1,
                                      "offset_seconds":0.6
                                    }
                                  ]
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.revision_number").value(1))
                .andExpect(jsonPath("$.summary.model_event_count").value(1))
                .andExpect(jsonPath("$.summary.human_event_count").value(1));
        verify(gateway).create(JOB_ID, command());
    }

    @Test
    void forwardsRegenerationRequestAndReturns202WithoutCompletionClaim() throws Exception {
        mockMvc.perform(post(
                        "/api/v1/transcriptions/{jobId}/revisions/" + "{revisionNumber}/regeneration-requests",
                        JOB_ID,
                        1))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.status").value("REQUESTED"))
                .andExpect(jsonPath("$.requested_artifacts[0]").value("midi"))
                .andExpect(jsonPath("$.requested_artifacts[1]").value("musicxml"))
                .andExpect(jsonPath("$.requested_artifacts[2]").value("svg"))
                .andExpect(jsonPath("$.completed").doesNotExist());
        verify(gateway).requestRegeneration(JOB_ID, 1);
    }

    @Test
    void malformedUuidAndConflictUseStablePublicErrors() throws Exception {
        mockMvc.perform(get("/api/v1/transcriptions/not-a-uuid/revisions"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INVALID_JOB_ID"));

        when(gateway.create(eq(JOB_ID), eq(command())))
                .thenThrow(new TranscriptionException(
                        UploadErrorCode.REVISION_CONFLICT,
                        "The transcription revision has changed.",
                        "base_revision_number"));
        mockMvc.perform(
                        post("/api/v1/transcriptions/{jobId}/revisions", JOB_ID)
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(
                                        """
                                {
                                  "base_revision_number":0,
                                  "operations":[
                                    {
                                      "type":"update",
                                      "event_id":"source-0",
                                      "written_pitch_midi":70,
                                      "onset_seconds":0.1,
                                      "offset_seconds":0.6
                                    }
                                  ]
                                }
                                """))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("REVISION_CONFLICT"))
                .andExpect(jsonPath("$.field").value("base_revision_number"));
    }

    @Test
    void corsAllowsFrontendGetAndPostWithoutCredentials() throws Exception {
        mockMvc.perform(options("/api/v1/transcriptions/{jobId}/revisions", JOB_ID)
                        .header("Origin", "http://localhost:3000")
                        .header("Access-Control-Request-Method", "POST"))
                .andExpect(status().isOk())
                .andExpect(header().string("Access-Control-Allow-Origin", "http://localhost:3000"))
                .andExpect(header().doesNotExist("Access-Control-Allow-Credentials"));
    }

    private static RevisionCreateCommand command() {
        return new RevisionCreateCommand(0, List.of(new RevisionUpdateOperation("source-0", 70, 0.1, 0.6)));
    }
}
