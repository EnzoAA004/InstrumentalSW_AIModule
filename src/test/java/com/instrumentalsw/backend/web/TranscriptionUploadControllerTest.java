package com.instrumentalsw.backend.web;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.matchesPattern;
import static org.hamcrest.Matchers.not;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.instrumentalsw.backend.application.TranscriptionGateway;
import com.instrumentalsw.backend.application.TranscriptionUpload;
import com.instrumentalsw.backend.configuration.UploadConfiguration;
import com.instrumentalsw.backend.domain.InputMode;
import com.instrumentalsw.backend.domain.SaxophoneType;
import com.instrumentalsw.backend.domain.TranscriptionException;
import com.instrumentalsw.backend.domain.TranscriptionJob;
import com.instrumentalsw.backend.domain.UploadErrorCode;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(TranscriptionUploadController.class)
@Import({UploadConfiguration.class, ApiExceptionHandler.class})
@ActiveProfiles("test")
class TranscriptionUploadControllerTest {
    private static final byte[] CONTENT = "synthetic-audio".getBytes(StandardCharsets.UTF_8);
    private static final UUID JOB_ID = UUID.fromString("11111111-1111-1111-1111-111111111111");

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private TranscriptionGateway gateway;

    @BeforeEach
    void configureGateway() {
        when(gateway.submit(any())).thenReturn(job("take.wav", "alto", "solo"));
    }

    @ParameterizedTest
    @ValueSource(strings = {"take.wav", "TAKE.WAV", "take.mp3", "TAKE.MP3"})
    void validMultipartReturns202AndPreservesEveryResponseField(String filename) throws Exception {
        when(gateway.submit(any())).thenReturn(job(filename, "alto", "solo"));

        mockMvc.perform(multipart("/api/v1/transcriptions")
                        .file(audio("file", filename, CONTENT))
                        .param("saxophone_type", "alto")
                        .param("input_mode", "solo"))
                .andExpect(status().isAccepted())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.job_id").value(JOB_ID.toString()))
                .andExpect(jsonPath("$.status").value("UPLOADED"))
                .andExpect(jsonPath("$.filename").value(filename))
                .andExpect(jsonPath("$.size_bytes").value(CONTENT.length))
                .andExpect(jsonPath("$.audio_sha256").value("a".repeat(64)))
                .andExpect(jsonPath("$.saxophone_type").value("alto"))
                .andExpect(jsonPath("$.input_mode").value("solo"));
    }

    @Test
    void exactMultipartNamesAndNormalizedFilenameReachGateway() throws Exception {
        when(gateway.submit(any())).thenReturn(job("take.wav", "tenor", "mixture"));

        mockMvc.perform(multipart("/api/v1/transcriptions")
                        .file(audio("file", "C:\\fakepath\\take.wav", CONTENT))
                        .param("saxophone_type", "tenor")
                        .param("input_mode", "mixture"))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.filename").value("take.wav"))
                .andExpect(jsonPath("$.filename").value(matchesPattern("^[^/\\\\]+$")));

        ArgumentCaptor<TranscriptionUpload> captor = ArgumentCaptor.forClass(TranscriptionUpload.class);
        verify(gateway).submit(captor.capture());
        TranscriptionUpload upload = captor.getValue();
        org.assertj.core.api.Assertions.assertThat(upload.filename()).isEqualTo("take.wav");
        org.assertj.core.api.Assertions.assertThat(upload.saxophoneType()).isEqualTo(SaxophoneType.TENOR);
        org.assertj.core.api.Assertions.assertThat(upload.inputMode()).isEqualTo(InputMode.MIXTURE);
        org.assertj.core.api.Assertions.assertThat(upload.content()).containsExactly(CONTENT);
    }

    @Test
    void missingFileUsesStableEnvelope() throws Exception {
        mockMvc.perform(multipart("/api/v1/transcriptions")
                        .param("saxophone_type", "alto")
                        .param("input_mode", "solo"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("AUDIO_FILE_REQUIRED"))
                .andExpect(jsonPath("$.message").value("An MP3 or WAV audio file is required."))
                .andExpect(jsonPath("$.field").value("file"));
    }

    @Test
    void wrongMultipartFileNameIsNotAcceptedAsThePublicContract() throws Exception {
        mockMvc.perform(multipart("/api/v1/transcriptions")
                        .file(audio("audio", "take.wav", CONTENT))
                        .param("saxophone_type", "alto")
                        .param("input_mode", "solo"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("AUDIO_FILE_REQUIRED"));
    }

    @Test
    void emptyFileUsesStableEnvelope() throws Exception {
        mockMvc.perform(multipart("/api/v1/transcriptions")
                        .file(audio("file", "take.wav", new byte[0]))
                        .param("saxophone_type", "alto")
                        .param("input_mode", "solo"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("EMPTY_AUDIO_FILE"))
                .andExpect(jsonPath("$.field").value("file"));
    }

    @Test
    void unsupportedExtensionReturns415() throws Exception {
        mockMvc.perform(multipart("/api/v1/transcriptions")
                        .file(audio("file", "score.pdf", CONTENT))
                        .param("saxophone_type", "alto")
                        .param("input_mode", "solo"))
                .andExpect(status().isUnsupportedMediaType())
                .andExpect(jsonPath("$.code").value("UNSUPPORTED_AUDIO_FORMAT"))
                .andExpect(jsonPath("$.message").value("Only MP3 and WAV files are supported."))
                .andExpect(jsonPath("$.field").value("file"));
    }

    @Test
    void invalidInstrumentReturnsStable400() throws Exception {
        mockMvc.perform(multipart("/api/v1/transcriptions")
                        .file(audio("file", "take.wav", CONTENT))
                        .param("saxophone_type", "clarinet")
                        .param("input_mode", "solo"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INVALID_SAXOPHONE_TYPE"))
                .andExpect(jsonPath("$.field").value("saxophone_type"));
    }

    @Test
    void invalidModeReturnsStable400() throws Exception {
        mockMvc.perform(multipart("/api/v1/transcriptions")
                        .file(audio("file", "take.wav", CONTENT))
                        .param("saxophone_type", "alto")
                        .param("input_mode", "stream"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INVALID_INPUT_MODE"))
                .andExpect(jsonPath("$.field").value("input_mode"));
    }

    @Test
    void controlledGatewayFailureDoesNotExposeInternalDetails() throws Exception {
        doThrow(new TranscriptionException(
                        UploadErrorCode.AI_SERVICE_UNAVAILABLE, "The transcription service is unavailable.", null))
                .when(gateway)
                .submit(any());

        mockMvc.perform(multipart("/api/v1/transcriptions")
                        .file(audio("file", "take.wav", CONTENT))
                        .param("saxophone_type", "alto")
                        .param("input_mode", "solo"))
                .andExpect(status().isBadGateway())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.code").value("AI_SERVICE_UNAVAILABLE"))
                .andExpect(jsonPath("$.message").value("The transcription service is unavailable."))
                .andExpect(jsonPath("$.field").doesNotExist())
                .andExpect(content().string(not(containsString("localhost:8000"))))
                .andExpect(content().string(not(containsString("synthetic-audio"))));
    }

    private static MockMultipartFile audio(String partName, String filename, byte[] content) {
        return new MockMultipartFile(partName, filename, "audio/wav", content);
    }

    private static TranscriptionJob job(String filename, String saxophoneType, String inputMode) {
        return new TranscriptionJob(
                JOB_ID,
                "UPLOADED",
                filename,
                CONTENT.length,
                "a".repeat(64),
                SaxophoneType.fromValue(saxophoneType),
                InputMode.fromValue(inputMode));
    }
}
