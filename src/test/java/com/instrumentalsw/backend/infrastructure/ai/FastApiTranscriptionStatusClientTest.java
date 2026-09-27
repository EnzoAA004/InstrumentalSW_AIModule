package com.instrumentalsw.backend.infrastructure.ai;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.instrumentalsw.backend.domain.InputMode;
import com.instrumentalsw.backend.domain.SaxophoneType;
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
import java.util.concurrent.Executors;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class FastApiTranscriptionStatusClientTest {
    private static final UUID JOB_ID = UUID.fromString("11111111-1111-1111-1111-111111111111");
    private HttpServer server;

    @AfterEach
    void stopServer() {
        if (server != null) {
            server.stop(0);
        }
    }

    @Test
    void forwardsExactGetWithoutMultipartAndParsesTheComplete200Response() throws Exception {
        RecordedRequest recorded = new RecordedRequest();
        start(exchange -> {
            recorded.method = exchange.getRequestMethod();
            recorded.path = exchange.getRequestURI().getRawPath();
            recorded.contentType = exchange.getRequestHeaders().getFirst("Content-Type");
            recorded.body = exchange.getRequestBody().readAllBytes();
            respond(exchange, 200, validJson());
        });

        var result = client(Duration.ofSeconds(1)).get(JOB_ID);

        assertThat(recorded.method).isEqualTo("GET");
        assertThat(recorded.path).isEqualTo("/api/v1/transcriptions/" + JOB_ID);
        assertThat(recorded.contentType).isNull();
        assertThat(recorded.body).isEmpty();
        assertThat(result.jobId()).isEqualTo(JOB_ID);
        assertThat(result.status()).isEqualTo("UPLOADED");
        assertThat(result.filename()).isEqualTo("take.wav");
        assertThat(result.sizeBytes()).isEqualTo(15);
        assertThat(result.audioSha256()).isEqualTo("a".repeat(64));
        assertThat(result.saxophoneType()).isEqualTo(SaxophoneType.ALTO);
        assertThat(result.inputMode()).isEqualTo(InputMode.SOLO);
    }

    @ParameterizedTest
    @CsvSource({
        "404,TRANSCRIPTION_NOT_FOUND,404",
        "422,INVALID_JOB_ID,400",
        "500,AI_SERVICE_ERROR,502",
        "503,AI_SERVICE_ERROR,502",
        "418,AI_SERVICE_ERROR,502"
    })
    void mapsStatusErrorsWithoutLeakingTheUpstreamBody(
            int upstreamStatus, UploadErrorCode expectedCode, int expectedPublicStatus) throws Exception {
        start(exchange -> respond(exchange, upstreamStatus, "<html>private upstream localhost:8000</html>"));

        assertThatThrownBy(() -> client().get(JOB_ID))
                .isInstanceOf(TranscriptionException.class)
                .satisfies(error -> {
                    TranscriptionException controlled = (TranscriptionException) error;
                    assertThat(controlled.code()).isEqualTo(expectedCode);
                    assertThat(controlled.publicStatus()).isEqualTo(expectedPublicStatus);
                    assertThat(controlled.getMessage()).doesNotContain("localhost", "<html>", "private upstream");
                    if (expectedCode == UploadErrorCode.TRANSCRIPTION_NOT_FOUND
                            || expectedCode == UploadErrorCode.INVALID_JOB_ID) {
                        assertThat(controlled.field()).isEqualTo("job_id");
                    }
                });
    }

    @Test
    void mapsReadTimeoutToUnavailable() throws Exception {
        start(exchange -> {
            try {
                Thread.sleep(300);
                respond(exchange, 200, validJson());
            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();
            }
        });

        assertControlledError(UploadErrorCode.AI_SERVICE_UNAVAILABLE, () -> client(Duration.ofMillis(50))
                .get(JOB_ID));
    }

    @Test
    void mapsConnectionRefusalToUnavailable() throws Exception {
        int unusedPort;
        try (ServerSocket socket = new ServerSocket(0)) {
            unusedPort = socket.getLocalPort();
        }
        FastApiTranscriptionClient refused = new FastApiTranscriptionClient(
                new AiServiceProperties(
                        "http://127.0.0.1:" + unusedPort, Duration.ofMillis(100), Duration.ofMillis(100)),
                new ObjectMapper());

        assertControlledError(UploadErrorCode.AI_SERVICE_UNAVAILABLE, () -> refused.get(JOB_ID));
    }

    @Test
    void rejectsMalformedJsonAsControlled502() throws Exception {
        start(exchange -> respond(exchange, 200, "{not-json"));
        assertControlledError(UploadErrorCode.AI_SERVICE_ERROR, () -> client().get(JOB_ID));
    }

    @Test
    void rejectsIncompatibleUuidAsControlled502() throws Exception {
        start(exchange -> respond(exchange, 200, validJson().replace(JOB_ID.toString(), "not-a-uuid")));
        assertControlledError(UploadErrorCode.AI_SERVICE_ERROR, () -> client().get(JOB_ID));
    }

    @Test
    void rejectsInvalidShaAsControlled502() throws Exception {
        start(exchange -> respond(exchange, 200, validJson().replace("a".repeat(64), "ABC123")));
        assertControlledError(UploadErrorCode.AI_SERVICE_ERROR, () -> client().get(JOB_ID));
    }

    @Test
    void rejectsInvalidSaxophoneEnumAsControlled502() throws Exception {
        start(exchange -> respond(exchange, 200, validJson().replace("\"alto\"", "\"clarinet\"")));
        assertControlledError(UploadErrorCode.AI_SERVICE_ERROR, () -> client().get(JOB_ID));
    }

    @Test
    void rejectsInvalidInputModeAsControlled502() throws Exception {
        start(exchange -> respond(exchange, 200, validJson().replace("\"solo\"", "\"stream\"")));
        assertControlledError(UploadErrorCode.AI_SERVICE_ERROR, () -> client().get(JOB_ID));
    }

    @Test
    void rejectsUnsafeFilenameAsControlled502() throws Exception {
        start(exchange -> respond(exchange, 200, validJson().replace("take.wav", "C:\\\\private\\\\take.wav")));
        assertControlledError(UploadErrorCode.AI_SERVICE_ERROR, () -> client().get(JOB_ID));
    }

    @Test
    void rejectsBlankStatusAsControlled502() throws Exception {
        start(exchange -> respond(exchange, 200, validJson().replace("UPLOADED", "   ")));
        assertControlledError(UploadErrorCode.AI_SERVICE_ERROR, () -> client().get(JOB_ID));
    }

    private FastApiTranscriptionClient client() {
        return client(Duration.ofSeconds(1));
    }

    private FastApiTranscriptionClient client(Duration timeout) {
        return new FastApiTranscriptionClient(new AiServiceProperties(baseUrl(), timeout, timeout), new ObjectMapper());
    }

    private void start(ExchangeHandler handler) throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/api/v1/transcriptions", handler::handle);
        server.setExecutor(Executors.newCachedThreadPool());
        server.start();
    }

    private String baseUrl() {
        return "http://127.0.0.1:" + server.getAddress().getPort();
    }

    private static void respond(HttpExchange exchange, int status, String body) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(status, bytes.length);
        exchange.getResponseBody().write(bytes);
        exchange.close();
    }

    private static String validJson() {
        return """
                {
                  "job_id": "11111111-1111-1111-1111-111111111111",
                  "status": "UPLOADED",
                  "filename": "take.wav",
                  "size_bytes": 15,
                  "audio_sha256": "%s",
                  "saxophone_type": "alto",
                  "input_mode": "solo"
                }
                """
                .formatted("a".repeat(64));
    }

    private static void assertControlledError(UploadErrorCode code, ThrowingCall call) {
        assertThatThrownBy(call::run).isInstanceOf(TranscriptionException.class).satisfies(error -> assertThat(
                        ((TranscriptionException) error).code())
                .isEqualTo(code));
    }

    @FunctionalInterface
    private interface ExchangeHandler {
        void handle(HttpExchange exchange) throws IOException;
    }

    @FunctionalInterface
    private interface ThrowingCall {
        void run() throws Exception;
    }

    private static final class RecordedRequest {
        private String method;
        private String path;
        private String contentType;
        private byte[] body;
    }
}
