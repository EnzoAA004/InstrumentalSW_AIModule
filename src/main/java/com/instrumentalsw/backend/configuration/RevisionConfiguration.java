package com.instrumentalsw.backend.configuration;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.instrumentalsw.backend.application.CreateTranscriptionRevision;
import com.instrumentalsw.backend.application.GetTranscriptionRevision;
import com.instrumentalsw.backend.application.GetTranscriptionRevisionHistory;
import com.instrumentalsw.backend.application.RequestTranscriptionRegeneration;
import com.instrumentalsw.backend.application.TranscriptionRevisionGateway;
import com.instrumentalsw.backend.infrastructure.ai.AiServiceProperties;
import com.instrumentalsw.backend.infrastructure.ai.FastApiTranscriptionRevisionClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
public class RevisionConfiguration {
    @Bean
    TranscriptionRevisionGateway transcriptionRevisionGateway(
            AiServiceProperties properties, ObjectMapper objectMapper) {
        return new FastApiTranscriptionRevisionClient(properties, objectMapper);
    }

    @Bean
    GetTranscriptionRevisionHistory getTranscriptionRevisionHistory(TranscriptionRevisionGateway gateway) {
        return new GetTranscriptionRevisionHistory(gateway);
    }

    @Bean
    GetTranscriptionRevision getTranscriptionRevision(TranscriptionRevisionGateway gateway) {
        return new GetTranscriptionRevision(gateway);
    }

    @Bean
    CreateTranscriptionRevision createTranscriptionRevision(TranscriptionRevisionGateway gateway) {
        return new CreateTranscriptionRevision(gateway);
    }

    @Bean
    RequestTranscriptionRegeneration requestTranscriptionRegeneration(TranscriptionRevisionGateway gateway) {
        return new RequestTranscriptionRegeneration(gateway);
    }
}
