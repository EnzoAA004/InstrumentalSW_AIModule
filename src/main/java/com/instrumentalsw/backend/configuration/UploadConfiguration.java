package com.instrumentalsw.backend.configuration;

import com.instrumentalsw.backend.application.GetTranscription;
import com.instrumentalsw.backend.application.SubmitTranscription;
import com.instrumentalsw.backend.application.TranscriptionGateway;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration(proxyBeanMethods = false)
@EnableConfigurationProperties(CorsProperties.class)
public class UploadConfiguration {
    @Bean
    SubmitTranscription submitTranscription(TranscriptionGateway gateway) {
        return new SubmitTranscription(gateway);
    }

    @Bean
    GetTranscription getTranscription(TranscriptionGateway gateway) {
        return new GetTranscription(gateway);
    }

    @Bean
    WebMvcConfigurer uploadCorsConfigurer(CorsProperties properties) {
        return new WebMvcConfigurer() {
            @Override
            public void addCorsMappings(CorsRegistry registry) {
                registry.addMapping("/api/v1/transcriptions/**")
                        .allowedOrigins(properties.origin())
                        .allowedMethods("POST", "GET", "OPTIONS")
                        .allowedHeaders("Content-Type")
                        .allowCredentials(false);
            }
        };
    }
}
