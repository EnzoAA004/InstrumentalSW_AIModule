package com.instrumentalsw.backend.configuration;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.instrumentalsw.backend.application.DownloadRevisionArtifact;
import com.instrumentalsw.backend.application.GetRevisionArtifacts;
import com.instrumentalsw.backend.application.TranscriptionArtifactGateway;
import com.instrumentalsw.backend.infrastructure.ai.AiServiceProperties;
import java.time.Duration;
import org.junit.jupiter.api.Test;

class ArtifactConfigurationTest {
    @Test
    void composesSeparateGatewayAndUseCases() {
        ArtifactConfiguration configuration = new ArtifactConfiguration();
        TranscriptionArtifactGateway gateway = configuration.transcriptionArtifactGateway(
                new AiServiceProperties("http://localhost:8000", Duration.ofSeconds(1), Duration.ofSeconds(1)),
                new ObjectMapper().findAndRegisterModules());

        GetRevisionArtifacts list = configuration.getRevisionArtifacts(gateway);
        DownloadRevisionArtifact download = configuration.downloadRevisionArtifact(gateway);

        assertThat(gateway).isNotNull();
        assertThat(list).isNotNull();
        assertThat(download).isNotNull();
    }
}
