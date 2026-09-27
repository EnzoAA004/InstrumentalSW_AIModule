package com.instrumentalsw.backend.configuration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.instrumentalsw.backend.infrastructure.ai.AiServiceProperties;
import java.time.Duration;
import org.junit.jupiter.api.Test;

class ConfigurationContractsTest {
    @Test
    void normalizesConfiguredOriginsAndServiceUrls() {
        assertThat(new CorsProperties("http://localhost:3000/").origin()).isEqualTo("http://localhost:3000");
        AiServiceProperties properties =
                new AiServiceProperties("http://localhost:8000/", Duration.ofSeconds(1), Duration.ofSeconds(2));
        assertThat(properties.baseUrl()).isEqualTo("http://localhost:8000");
        assertThat(properties.connectTimeout()).isEqualTo(Duration.ofSeconds(1));
        assertThat(properties.readTimeout()).isEqualTo(Duration.ofSeconds(2));
    }

    @Test
    void rejectsBlankOriginsAndInvalidAiTimeouts() {
        assertThatThrownBy(() -> new CorsProperties(" ")).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new AiServiceProperties(" ", Duration.ofSeconds(1), Duration.ofSeconds(1)))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new AiServiceProperties("http://localhost:8000", Duration.ZERO, Duration.ofSeconds(1)))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() ->
                        new AiServiceProperties("http://localhost:8000", Duration.ofSeconds(1), Duration.ofSeconds(-1)))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
