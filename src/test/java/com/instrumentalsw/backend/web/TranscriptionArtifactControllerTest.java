package com.instrumentalsw.backend.web;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.instrumentalsw.backend.application.DownloadRevisionArtifact;
import com.instrumentalsw.backend.application.GetRevisionArtifacts;
import com.instrumentalsw.backend.domain.ArtifactType;
import com.instrumentalsw.backend.domain.RevisionArtifactDescriptor;
import com.instrumentalsw.backend.domain.RevisionArtifactDownload;
import com.instrumentalsw.backend.domain.RevisionArtifactList;
import com.instrumentalsw.backend.domain.TranscriptionException;
import com.instrumentalsw.backend.domain.UploadErrorCode;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

class TranscriptionArtifactControllerTest {
    private static final UUID JOB_ID = UUID.fromString("11111111-1111-1111-1111-111111111111");
    private static final String SHA = "9f64a747e1b97f131fabb6b447296c9b6f0201e79fb3c5356e6c77e89b6a806a";
    private final GetRevisionArtifacts listArtifacts = mock(GetRevisionArtifacts.class);
    private final DownloadRevisionArtifact downloadArtifact = mock(DownloadRevisionArtifact.class);
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.standaloneSetup(new TranscriptionArtifactController(listArtifacts, downloadArtifact))
                .setControllerAdvice(new ApiExceptionHandler())
                .build();
    }

    @Test
    void exposesMetadataAndBinaryWithExactPublicHeaders() throws Exception {
        var descriptor = descriptor();
        when(listArtifacts.execute(JOB_ID, 2)).thenReturn(new RevisionArtifactList(JOB_ID, 2, List.of(descriptor)));
        when(downloadArtifact.execute(JOB_ID, 2, "midi"))
                .thenReturn(new RevisionArtifactDownload(descriptor, new byte[] {1, 2, 3, 4}));

        mockMvc.perform(get("/api/v1/transcriptions/{jobId}/revisions/{revision}/artifacts", JOB_ID, 2))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.job_id").value(JOB_ID.toString()))
                .andExpect(jsonPath("$.revision_number").value(2))
                .andExpect(jsonPath("$.artifacts[0].artifact_type").value("midi"))
                .andExpect(jsonPath("$.artifacts[0].sha256").value(SHA))
                .andExpect(jsonPath("$.artifacts[0].content").doesNotExist());

        mockMvc.perform(get(
                        "/api/v1/transcriptions/{jobId}/revisions/{revision}/artifacts/{artifactId}",
                        JOB_ID,
                        2,
                        "midi"))
                .andExpect(status().isOk())
                .andExpect(content().bytes(new byte[] {1, 2, 3, 4}))
                .andExpect(header().string("Content-Type", "audio/midi"))
                .andExpect(header().string("Content-Disposition", "attachment; filename=\"transcription-r2.mid\""))
                .andExpect(header().string("Content-Length", "4"))
                .andExpect(header().string("Cache-Control", "private, no-store"))
                .andExpect(header().string("X-Content-Type-Options", "nosniff"))
                .andExpect(header().string("X-Content-SHA256", SHA));
        verify(listArtifacts).execute(JOB_ID, 2);
        verify(downloadArtifact).execute(JOB_ID, 2, "midi");
    }

    @Test
    void stableErrorsAndReadOnlyMethodsAreExposed() throws Exception {
        when(listArtifacts.execute(JOB_ID, 2))
                .thenThrow(new TranscriptionException(
                        UploadErrorCode.ARTIFACTS_NOT_READY,
                        "Artifacts are not available for this revision yet.",
                        "revision_number"));

        mockMvc.perform(get("/api/v1/transcriptions/{jobId}/revisions/{revision}/artifacts", JOB_ID, 2))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("ARTIFACTS_NOT_READY"))
                .andExpect(jsonPath("$.field").value("revision_number"));
        mockMvc.perform(get("/api/v1/transcriptions/not-a-uuid/revisions/2/artifacts"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INVALID_JOB_ID"));
        mockMvc.perform(post("/api/v1/transcriptions/{jobId}/revisions/2/artifacts", JOB_ID))
                .andExpect(status().isMethodNotAllowed());
    }

    @Test
    void rejectsNegativeNonNumericAndNonCanonicalRevisionPaths() throws Exception {
        mockMvc.perform(get("/api/v1/transcriptions/{jobId}/revisions/-1/artifacts", JOB_ID))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("REVISION_NOT_FOUND"));
        mockMvc.perform(get("/api/v1/transcriptions/{jobId}/revisions/not-a-number/artifacts", JOB_ID))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("REVISION_NOT_FOUND"));
        mockMvc.perform(get("/api/v1/transcriptions/{jobId}/revisions/02/artifacts/midi", JOB_ID))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("REVISION_NOT_FOUND"));
    }

    private static RevisionArtifactDescriptor descriptor() {
        return new RevisionArtifactDescriptor(
                "midi", ArtifactType.MIDI, "transcription-r2.mid", "audio/midi", ".mid", 4, SHA, 0);
    }
}
