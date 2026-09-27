package com.instrumentalsw.backend.configuration;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.instrumentalsw.backend.application.GetTranscriptionReview;
import com.instrumentalsw.backend.application.TranscriptionReviewGateway;
import com.instrumentalsw.backend.infrastructure.ai.AiServiceProperties;
import com.instrumentalsw.backend.infrastructure.ai.FastApiTranscriptionReviewClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
public class ReviewConfiguration {
    @Bean
    TranscriptionReviewGateway transcriptionReviewGateway(AiServiceProperties properties, ObjectMapper objectMapper) {
        return new FastApiTranscriptionReviewClient(properties, objectMapper);
    }

    @Bean
    GetTranscriptionReview getTranscriptionReview(TranscriptionReviewGateway gateway) {
        return new GetTranscriptionReview(gateway);
    }
}
