package com.instrumentalsw.backend.infrastructure.ai;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "saxo.ai")
public record AiServiceProperties(String baseUrl, Duration connectTimeout, Duration readTimeout) {
    public AiServiceProperties {
        if (baseUrl == null || baseUrl.isBlank()) {
            throw new IllegalArgumentException("saxo.ai.base-url must not be blank");
        }
        if (connectTimeout == null || connectTimeout.isNegative() || connectTimeout.isZero()) {
            throw new IllegalArgumentException("connect timeout must be positive");
        }
        if (readTimeout == null || readTimeout.isNegative() || readTimeout.isZero()) {
            throw new IllegalArgumentException("read timeout must be positive");
        }
        baseUrl = baseUrl.replaceAll("/+$", "");
    }
}
