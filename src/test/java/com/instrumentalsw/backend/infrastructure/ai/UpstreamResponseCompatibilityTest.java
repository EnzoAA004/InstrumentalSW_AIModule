package com.instrumentalsw.backend.infrastructure.ai;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.instrumentalsw.backend.application.TranscriptionUpload;
import com.instrumentalsw.backend.domain.InputMode;
import com.instrumentalsw.backend.domain.SaxophoneType;
import com.instrumentalsw.backend.domain.TranscriptionException;
import com.instrumentalsw.backend.domain.UploadErrorCode;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

class UpstreamResponseCompatibilityTest {
    private HttpServer server;

    @AfterEach
    void stopServer() {
        if (server != null) {
            server.stop(0);
        }
    }

    @Test
    void treatsUnknownUpstreamSaxophoneAsControlled502() throws Exception {
        start(validJson().replace("\"alto\"", "\"clarinet\""));

        assertIncompatibleResponse();
    }

    @Test
    void treatsUnknownUpstreamInputModeAsControlled502() throws Exception {
        start(validJson().replace("\"solo\"", "\"stream\""));

        assertIncompatibleResponse();
    }

    private void assertIncompatibleResponse() {
        FastApiTranscriptionClient client = new FastApiTranscriptionClient(
                new AiServiceProperties(
                        "http://127.0.0.1:" + server.getAddress().getPort(),
                        Duration.ofSeconds(1),
                        Duration.ofSeconds(1)),
                new ObjectMapper());

        assertThatThrownBy(() -> client.submit(upload()))
                .isInstanceOf(TranscriptionException.class)
                .satisfies(error -> {
                    TranscriptionException controlled = (TranscriptionException) error;
                    org.assertj.core.api.Assertions.assertThat(controlled.code())
                            .isEqualTo(UploadErrorCode.AI_SERVICE_ERROR);
                    org.assertj.core.api.Assertions.assertThat(controlled.publicStatus())
                            .isEqualTo(502);
                });
    }

    private void start(String responseBody) throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/api/v1/transcriptions", exchange -> respond(exchange, responseBody));
        server.start();
    }

    private static void respond(HttpExchange exchange, String body) throws IOException {
        exchange.getRequestBody().readAllBytes();
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(202, bytes.length);
        exchange.getResponseBody().write(bytes);
        exchange.close();
    }

    private static TranscriptionUpload upload() {
        return new TranscriptionUpload(
                "take.wav", "audio/wav", new byte[] {1, 2, 3}, SaxophoneType.ALTO, InputMode.SOLO);
    }

    private static String validJson() {
        return """
                {
                  "job_id": "11111111-1111-1111-1111-111111111111",
                  "status": "UPLOADED",
                  "filename": "take.wav",
                  "size_bytes": 3,
                  "audio_sha256": "%s",
                  "saxophone_type": "alto",
                  "input_mode": "solo"
                }
                """
                .formatted("a".repeat(64));
    }
}
