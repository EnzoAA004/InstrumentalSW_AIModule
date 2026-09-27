package com.instrumentalsw.backend.configuration;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.instrumentalsw.backend.application.TranscriptionGateway;
import com.instrumentalsw.backend.infrastructure.ai.AiServiceProperties;
import com.instrumentalsw.backend.infrastructure.ai.FastApiTranscriptionClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
public class AiClientConfiguration {
    @Bean
    TranscriptionGateway transcriptionGateway(AiServiceProperties properties, ObjectMapper objectMapper) {
        return new FastApiTranscriptionClient(properties, objectMapper);
    }
}
