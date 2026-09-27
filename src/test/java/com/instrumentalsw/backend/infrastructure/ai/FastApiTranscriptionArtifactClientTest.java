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
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.HexFormat;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

class FastApiTranscriptionArtifactClientTest {
    private static final UUID JOB_ID = UUID.fromString("11111111-1111-1111-1111-111111111111");
    private static final String BASE_PATH =
            "/api/v1/transcriptions/11111111-1111-1111-1111-111111111111/revisions/2/artifacts";
    private static final byte[] MIDI = new byte[] {1, 2, 3, 4};
    private static final String SHA = HexFormat.of().formatHex(sha256(MIDI));
    private HttpServer server;

    @AfterEach
    void stop() {
        if (server != null) {
            server.stop(0);
        }
    }

    @Test
    void forwardsBodylessGetAndValidatesCompleteMetadata() throws Exception {
        Recorded request = new Recorded();
        start(exchange -> {
            request.method = exchange.getRequestMethod();
            request.path = exchange.getRequestURI().getPath();
            request.body = exchange.getRequestBody().readAllBytes();
            json(exchange, 200, listJson());
        });

        var result = client(Duration.ofSeconds(1)).list(JOB_ID, 2);

        assertThat(request.method).isEqualTo("GET");
        assertThat(request.path).isEqualTo(BASE_PATH);
        assertThat(request.body).isEmpty();
        assertThat(result.jobId()).isEqualTo(JOB_ID);
        assertThat(result.revisionNumber()).isEqualTo(2);
        assertThat(result.artifacts()).hasSize(1);
        assertThat(result.artifacts().getFirst().artifactId()).isEqualTo("midi");
        assertThat(result.artifacts().getFirst().sha256()).isEqualTo(SHA);
    }

    @Test
    void downloadsExactBinaryAndValidatesAuthoritativeHeadersSizeAndSha() throws Exception {
        start(exchange -> {
            assertThat(exchange.getRequestMethod()).isEqualTo("GET");
            if (exchange.getRequestURI().getPath().equals(BASE_PATH)) {
                json(exchange, 200, listJson());
                return;
            }
            assertThat(exchange.getRequestURI().getPath()).isEqualTo(BASE_PATH + "/midi");
            binary(exchange, "audio/midi", "transcription-r2.mid", SHA);
        });

        var result = client(Duration.ofSeconds(1)).download(JOB_ID, 2, "midi");

        assertThat(result.content()).containsExactly(MIDI);
        assertThat(result.descriptor().filename()).isEqualTo("transcription-r2.mid");
        assertThat(result.descriptor().mediaType()).isEqualTo("audio/midi");
        assertThat(result.descriptor().sizeBytes()).isEqualTo(MIDI.length);
        assertThat(result.descriptor().sha256()).isEqualTo(SHA);
    }

    @Test
    void rejectsIncompatibleBinaryAndMapsStableErrors() throws Exception {
        start(exchange -> {
            if (exchange.getRequestURI().getPath().equals(BASE_PATH)) {
                json(exchange, 200, listJson());
                return;
            }
            binary(exchange, "image/svg+xml", "wrong.svg", "0".repeat(64));
        });
        assertCode(UploadErrorCode.AI_SERVICE_ERROR, () -> client(Duration.ofSeconds(1))
                .download(JOB_ID, 2, "midi"));
        stop();
        server = null;

        start(exchange -> json(
                exchange,
                409,
                "{\"code\":\"ARTIFACTS_NOT_READY\",\"message\":\"safe\",\"field\":\"revision_number\"}"));
        assertCode(UploadErrorCode.ARTIFACTS_NOT_READY, () -> client(Duration.ofSeconds(1))
                .list(JOB_ID, 2));
    }

    private FastApiTranscriptionArtifactClient client(Duration readTimeout) {
        return new FastApiTranscriptionArtifactClient(
                new AiServiceProperties(
                        "http://localhost:" + server.getAddress().getPort(), Duration.ofSeconds(1), readTimeout),
                new ObjectMapper().findAndRegisterModules());
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

    private static void binary(HttpExchange exchange, String mediaType, String filename, String sha)
            throws IOException {
        exchange.getResponseHeaders().add("Content-Type", mediaType);
        exchange.getResponseHeaders().add("Content-Disposition", "attachment; filename=\"" + filename + "\"");
        exchange.getResponseHeaders().add("X-Content-SHA256", sha);
        exchange.getResponseHeaders().add("Cache-Control", "private, no-store");
        exchange.getResponseHeaders().add("X-Content-Type-Options", "nosniff");
        exchange.sendResponseHeaders(200, MIDI.length);
        exchange.getResponseBody().write(MIDI);
        exchange.close();
    }

    private static String listJson() {
        return """
                {
                  "job_id":"11111111-1111-1111-1111-111111111111",
                  "revision_number":2,
                  "artifacts":[{
                    "artifact_id":"midi",
                    "artifact_type":"midi",
                    "filename":"transcription-r2.mid",
                    "media_type":"audio/midi",
                    "extension":".mid",
                    "size_bytes":4,
                    "sha256":"%s",
                    "order":0
                  }]
                }
                """
                .formatted(SHA);
    }

    private static byte[] sha256(byte[] bytes) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(bytes);
        } catch (Exception error) {
            throw new IllegalStateException(error);
        }
    }

    private static void assertCode(UploadErrorCode code, Runnable operation) {
        assertThatThrownBy(operation::run)
                .isInstanceOf(TranscriptionException.class)
                .satisfies(error ->
                        assertThat(((TranscriptionException) error).code()).isEqualTo(code));
    }

    private interface Handler {
        void handle(HttpExchange exchange) throws IOException;
    }

    private static final class Recorded {
        private String method;
        private String path;
        private byte[] body;
    }
}
