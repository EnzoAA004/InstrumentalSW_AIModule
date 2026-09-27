package com.instrumentalsw.backend.configuration;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "saxo.frontend")
public record CorsProperties(String origin) {
    public CorsProperties {
        if (origin == null || origin.isBlank()) {
            throw new IllegalArgumentException("saxo.frontend.origin must not be blank");
        }
        origin = origin.replaceAll("/+$", "");
    }
}
