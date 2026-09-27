package com.instrumentalsw.backend.configuration;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.instrumentalsw.backend.application.DownloadRevisionArtifact;
import com.instrumentalsw.backend.application.GetRevisionArtifacts;
import com.instrumentalsw.backend.application.TranscriptionArtifactGateway;
import com.instrumentalsw.backend.infrastructure.ai.AiServiceProperties;
import com.instrumentalsw.backend.infrastructure.ai.FastApiTranscriptionArtifactClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
public class ArtifactConfiguration {
    @Bean
    TranscriptionArtifactGateway transcriptionArtifactGateway(
            AiServiceProperties properties, ObjectMapper objectMapper) {
        return new FastApiTranscriptionArtifactClient(properties, objectMapper);
    }

    @Bean
    GetRevisionArtifacts getRevisionArtifacts(TranscriptionArtifactGateway gateway) {
        return new GetRevisionArtifacts(gateway);
    }

    @Bean
    DownloadRevisionArtifact downloadRevisionArtifact(TranscriptionArtifactGateway gateway) {
        return new DownloadRevisionArtifact(gateway);
    }
}
