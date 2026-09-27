package com.instrumentalsw.backend.infrastructure.ai;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.instrumentalsw.backend.domain.TranscriptionException;
import com.instrumentalsw.backend.domain.UploadErrorCode;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;

class FastApiTranscriptionArtifactFailuresTest {
    private static final UUID JOB_ID = UUID.fromString("11111111-1111-1111-1111-111111111111");
    private HttpServer server;

    @AfterEach
    void stop() {
        if (server != null) {
            server.stop(0);
        }
    }

    @ParameterizedTest
    @MethodSource("stableErrors")
    void mapsStablePublicErrors(int status, String code, UploadErrorCode expected) throws Exception {
        start(exchange -> json(
                exchange,
                status,
                "{\"code\":\"" + code + "\",\"message\":\"private upstream text\",\"field\":\"job_id\"}"));

        assertCode(expected, () -> client(baseUrl(), Duration.ofSeconds(1)).list(JOB_ID, 2));
    }

    static java.util.stream.Stream<Arguments> stableErrors() {
        return java.util.stream.Stream.of(
                Arguments.of(400, "INVALID_JOB_ID", UploadErrorCode.INVALID_JOB_ID),
                Arguments.of(404, "TRANSCRIPTION_NOT_FOUND", UploadErrorCode.TRANSCRIPTION_NOT_FOUND),
                Arguments.of(404, "REVISION_NOT_FOUND", UploadErrorCode.REVISION_NOT_FOUND),
                Arguments.of(404, "ARTIFACT_NOT_FOUND", UploadErrorCode.ARTIFACT_NOT_FOUND),
                Arguments.of(409, "ARTIFACTS_NOT_READY", UploadErrorCode.ARTIFACTS_NOT_READY));
    }

    @Test
    void convertsFiveHundredMalformedAndUnexpectedStatusesToControlledServiceError() throws Exception {
        start(exchange -> json(exchange, 500, "secret"));
        assertCode(UploadErrorCode.AI_SERVICE_ERROR, () -> client(baseUrl(), Duration.ofSeconds(1))
                .list(JOB_ID, 2));
        stop();
        server = null;

        start(exchange -> json(exchange, 200, "{not-json"));
        assertCode(UploadErrorCode.AI_SERVICE_ERROR, () -> client(baseUrl(), Duration.ofSeconds(1))
                .list(JOB_ID, 2));
        stop();
        server = null;

        start(exchange -> json(exchange, 418, "{\"code\":\"ARTIFACTS_NOT_READY\",\"message\":\"x\",\"field\":null}"));
        assertCode(UploadErrorCode.AI_SERVICE_ERROR, () -> client(baseUrl(), Duration.ofSeconds(1))
                .list(JOB_ID, 2));
    }

    @Test
    void mapsReadTimeoutAndRefusedConnectionToUnavailable() throws Exception {
        start(exchange -> {
            try {
                Thread.sleep(200);
            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();
            }
            json(exchange, 200, "{}");
        });
        assertCode(UploadErrorCode.AI_SERVICE_UNAVAILABLE, () -> client(baseUrl(), Duration.ofMillis(20))
                .list(JOB_ID, 2));
        stop();
        server = null;

        int unusedPort;
        try (ServerSocket socket = new ServerSocket(0)) {
            unusedPort = socket.getLocalPort();
        }
        assertCode(UploadErrorCode.AI_SERVICE_UNAVAILABLE, () -> client(
                        "http://localhost:" + unusedPort, Duration.ofMillis(100))
                .list(JOB_ID, 2));
    }

    private FastApiTranscriptionArtifactClient client(String url, Duration readTimeout) {
        return new FastApiTranscriptionArtifactClient(
                new AiServiceProperties(url, Duration.ofMillis(100), readTimeout),
                new ObjectMapper().findAndRegisterModules());
    }

    private String baseUrl() {
        return "http://localhost:" + server.getAddress().getPort();
    }

    private void start(Handler handler) throws IOException {
        server = HttpServer.create(new InetSocketAddress("localhost", 0), 0);
        server.createContext("/", exchange -> handler.handle(exchange));
        server.start();
    }

    private static void json(HttpExchange exchange, int status, String body) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().add("Content-Type", "application/json");
        exchange.sendResponseHeaders(status, bytes.length);
        exchange.getResponseBody().write(bytes);
        exchange.close();
    }

    private static void assertCode(UploadErrorCode code, Runnable operation) {
        assertThatThrownBy(operation::run)
                .isInstanceOf(TranscriptionException.class)
                .satisfies(error ->
                        assertThat(((TranscriptionException) error).code()).isEqualTo(code))
                .hasMessageNotContaining("private upstream text")
                .hasMessageNotContaining("secret");
    }

    private interface Handler {
        void handle(HttpExchange exchange) throws IOException;
    }
}
