package com.instrumentalsw.backend.web;

import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.instrumentalsw.backend.application.RevisionAddOperation;
import com.instrumentalsw.backend.application.RevisionCreateCommand;
import com.instrumentalsw.backend.application.RevisionDeleteOperation;
import com.instrumentalsw.backend.application.TranscriptionGateway;
import com.instrumentalsw.backend.application.TranscriptionRevisionGateway;
import com.instrumentalsw.backend.configuration.RevisionConfiguration;
import com.instrumentalsw.backend.configuration.UploadConfiguration;
import java.util.List;
import java.util.UUID;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
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
class TranscriptionRevisionControllerValidationTest {
    private static final UUID JOB_ID = UUID.fromString("11111111-1111-1111-1111-111111111111");

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private TranscriptionRevisionGateway gateway;

    @MockitoBean
    private TranscriptionGateway uploadGateway;

    @ParameterizedTest
    @MethodSource("invalidRevisionNumbers")
    void rejectsNonCanonicalRevisionNumbers(String revisionNumber) throws Exception {
        mockMvc.perform(get("/api/v1/transcriptions/{jobId}/revisions/{revisionNumber}", JOB_ID, revisionNumber))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("REVISION_NOT_FOUND"))
                .andExpect(jsonPath("$.field").value("revision_number"));
    }

    static Stream<String> invalidRevisionNumbers() {
        return Stream.of("-1", "01", "not-a-number");
    }

    @ParameterizedTest
    @MethodSource("invalidOperationBodies")
    void rejectsStructurallyInvalidOperationBodies(String body, String expectedCode, String expectedField)
            throws Exception {
        mockMvc.perform(post("/api/v1/transcriptions/{jobId}/revisions", JOB_ID)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value(expectedCode))
                .andExpect(jsonPath("$.field").value(expectedField));
    }

    static Stream<Arguments> invalidOperationBodies() {
        return Stream.of(
                Arguments.of("{}", "INVALID_REVISION_OPERATION", "operations"),
                Arguments.of(
                        """
                        {
                          "base_revision_number":-1,
                          "operations":[{"type":"delete","event_id":"source-0"}]
                        }
                        """,
                        "INVALID_REVISION_OPERATION",
                        "base_revision_number"),
                Arguments.of(
                        """
                        {"base_revision_number":0,"operations":[]}
                        """,
                        "INVALID_REVISION_OPERATION",
                        "operations"),
                Arguments.of(
                        """
                        {"base_revision_number":0,"operations":["delete"]}
                        """,
                        "INVALID_REVISION_OPERATION",
                        "operations"),
                Arguments.of(
                        """
                        {
                          "base_revision_number":0,
                          "operations":[{"type":"move","event_id":"source-0"}]
                        }
                        """,
                        "INVALID_REVISION_OPERATION",
                        "operations"),
                Arguments.of(
                        """
                        {
                          "base_revision_number":0,
                          "operations":[
                            {
                              "type":"update",
                              "event_id":"source-0",
                              "written_pitch_midi":70,
                              "onset_seconds":0.1
                            }
                          ]
                        }
                        """,
                        "INVALID_REVISION_OPERATION",
                        "operations"),
                Arguments.of(
                        """
                        {
                          "base_revision_number":0,
                          "operations":[
                            {"type":"add","written_pitch_midi":72,"onset_seconds":0.1}
                          ]
                        }
                        """,
                        "INVALID_REVISION_OPERATION",
                        "operations"),
                Arguments.of(
                        """
                        {
                          "base_revision_number":0,
                          "operations":[
                            {"type":"delete","event_id":"source-0","velocity":64}
                          ]
                        }
                        """,
                        "INVALID_REVISION_OPERATION",
                        "operations"),
                Arguments.of(
                        """
                        {"base_revision_number":0,"operations":[{"type":"delete","event_id":""}]}
                        """,
                        "INVALID_REVISION_OPERATION",
                        "operations"),
                Arguments.of(
                        """
                        {
                          "base_revision_number":0,
                          "operations":[
                            {
                              "type":"add",
                              "written_pitch_midi":128,
                              "onset_seconds":0.1,
                              "offset_seconds":0.5
                            }
                          ]
                        }
                        """,
                        "INVALID_REVISION_EVENT",
                        "operations"),
                Arguments.of(
                        """
                        {
                          "base_revision_number":0,
                          "operations":[
                            {
                              "type":"add",
                              "written_pitch_midi":72,
                              "onset_seconds":-0.1,
                              "offset_seconds":0.5
                            }
                          ]
                        }
                        """,
                        "INVALID_REVISION_EVENT",
                        "operations"),
                Arguments.of(
                        """
                        {
                          "base_revision_number":0,
                          "operations":[
                            {
                              "type":"update",
                              "event_id":"source-0",
                              "written_pitch_midi":70,
                              "onset_seconds":0.1,
                              "offset_seconds":0.5
                            },
                            {"type":"delete","event_id":"source-0"}
                          ]
                        }
                        """,
                        "INVALID_REVISION_OPERATION",
                        "operations"));
    }

    @Test
    void acceptsAddWithDefaultAndExplicitVelocityThenDelete() throws Exception {
        RevisionCreateCommand expected = new RevisionCreateCommand(
                0,
                List.of(
                        new RevisionAddOperation(72, 0.7, 1.0, 64),
                        new RevisionAddOperation(74, 1.1, 1.4, 45),
                        new RevisionDeleteOperation("source-1")));
        var revision = TranscriptionRevisionUseCasesFixture.revision();
        when(gateway.create(eq(JOB_ID), eq(expected))).thenReturn(revision);

        mockMvc.perform(
                        post("/api/v1/transcriptions/{jobId}/revisions", JOB_ID)
                                .contentType(MediaType.APPLICATION_JSON)
                                .content(
                                        """
                                {
                                  "base_revision_number":0,
                                  "operations":[
                                    {
                                      "type":"add",
                                      "written_pitch_midi":72,
                                      "onset_seconds":0.7,
                                      "offset_seconds":1.0
                                    },
                                    {
                                      "type":"add",
                                      "written_pitch_midi":74,
                                      "onset_seconds":1.1,
                                      "offset_seconds":1.4,
                                      "velocity":45
                                    },
                                    {"type":"delete","event_id":"source-1"}
                                  ]
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.revision_number").value(1));

        verify(gateway).create(JOB_ID, expected);
    }
}
