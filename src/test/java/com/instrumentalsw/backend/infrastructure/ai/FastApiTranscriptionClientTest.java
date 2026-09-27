package com.instrumentalsw.backend.infrastructure.ai;

import static org.assertj.core.api.Assertions.assertThat;
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
import java.net.ServerSocket;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.Executors;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class FastApiTranscriptionClientTest {
    private static final byte[] CONTENT = "synthetic-audio".getBytes(StandardCharsets.UTF_8);
    private static final Pattern PART_NAME =
            Pattern.compile("Content-Disposition:[^\\r\\n]*\\bname=\\\"([^\\\"]+)\\\"");
    private HttpServer server;

    @AfterEach
    void stopServer() {
        if (server != null) {
            server.stop(0);
        }
    }

    @Test
    void forwardsExactRealMultipartAndParsesComplete202Response() throws Exception {
        RecordedRequest recorded = new RecordedRequest();
        start(exchange -> {
            recorded.method = exchange.getRequestMethod();
            recorded.path = exchange.getRequestURI().getPath();
            recorded.contentType = exchange.getRequestHeaders().getFirst("Content-Type");
            recorded.body = exchange.getRequestBody().readAllBytes();
            respond(exchange, 202, validJson());
        });

        var result = client(Duration.ofSeconds(1)).submit(upload());

        assertThat(recorded.method).isEqualTo("POST");
        assertThat(recorded.path).isEqualTo("/api/v1/transcriptions");
        assertThat(recorded.contentType).startsWith("multipart/form-data;boundary=");
        String body = new String(recorded.body, StandardCharsets.ISO_8859_1);
        assertThat(partNames(body)).containsExactlyInAnyOrder("file", "saxophone_type", "input_mode");
        assertThat(body)
                .contains("filename=\"take.wav\"")
                .contains("Content-Type: audio/wav")
                .contains("synthetic-audio")
                .contains("\r\n\r\nalto\r\n")
                .contains("\r\n\r\nsolo\r\n");
        assertThat(result.jobId().toString()).isEqualTo("11111111-1111-1111-1111-111111111111");
        assertThat(result.status()).isEqualTo("UPLOADED");
        assertThat(result.filename()).isEqualTo("take.wav");
        assertThat(result.sizeBytes()).isEqualTo(CONTENT.length);
        assertThat(result.audioSha256()).isEqualTo("a".repeat(64));
        assertThat(result.saxophoneType()).isEqualTo(SaxophoneType.ALTO);
        assertThat(result.inputMode()).isEqualTo(InputMode.SOLO);
    }

    @ParameterizedTest
    @CsvSource({
        "400,INVALID_TRANSCRIPTION_REQUEST",
        "413,AUDIO_SIZE_LIMIT_EXCEEDED",
        "415,UNSUPPORTED_AUDIO_FORMAT",
        "422,INVALID_TRANSCRIPTION_REQUEST",
        "500,AI_SERVICE_ERROR",
        "503,AI_SERVICE_ERROR"
    })
    void mapsUpstreamStatusesWithoutLeakingBody(int status, UploadErrorCode code) throws Exception {
        start(exchange -> respond(exchange, status, "<html>private upstream localhost:8000</html>"));

        assertThatThrownBy(() -> client(Duration.ofSeconds(1)).submit(upload()))
                .isInstanceOf(TranscriptionException.class)
                .satisfies(error -> {
                    TranscriptionException controlled = (TranscriptionException) error;
                    assertThat(controlled.code()).isEqualTo(code);
                    assertThat(controlled.getMessage()).doesNotContain("localhost", "<html>");
                });
    }

    @Test
    void rejectsMalformedJsonAsControlled502() throws Exception {
        start(exchange -> respond(exchange, 202, "{not-json"));
        assertControlledError(UploadErrorCode.AI_SERVICE_ERROR, () -> client().submit(upload()));
    }

    @Test
    void rejectsInvalidUuidAsControlled502() throws Exception {
        start(exchange ->
                respond(exchange, 202, validJson().replace("11111111-1111-1111-1111-111111111111", "not-a-uuid")));
        assertControlledError(UploadErrorCode.AI_SERVICE_ERROR, () -> client().submit(upload()));
    }

    @Test
    void rejectsInvalidShaAsControlled502() throws Exception {
        start(exchange -> respond(exchange, 202, validJson().replace("a".repeat(64), "ABC123")));
        assertControlledError(UploadErrorCode.AI_SERVICE_ERROR, () -> client().submit(upload()));
    }

    @Test
    void rejectsResponseFilenameContainingClientPath() throws Exception {
        start(exchange -> respond(exchange, 202, validJson().replace("take.wav", "C:\\\\private\\\\take.wav")));
        assertControlledError(UploadErrorCode.AI_SERVICE_ERROR, () -> client().submit(upload()));
    }

    @Test
    void mapsReadTimeoutToUnavailable() throws Exception {
        start(exchange -> {
            try {
                Thread.sleep(300);
                respond(exchange, 202, validJson());
            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();
            }
        });
        assertControlledError(UploadErrorCode.AI_SERVICE_UNAVAILABLE, () -> client(Duration.ofMillis(50))
                .submit(upload()));
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
        assertControlledError(UploadErrorCode.AI_SERVICE_UNAVAILABLE, () -> refused.submit(upload()));
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

    private static Set<String> partNames(String body) {
        Set<String> names = new HashSet<>();
        Matcher matcher = PART_NAME.matcher(body);
        while (matcher.find()) {
            names.add(matcher.group(1));
        }
        return names;
    }

    private static TranscriptionUpload upload() {
        return new TranscriptionUpload("take.wav", "audio/wav", CONTENT, SaxophoneType.ALTO, InputMode.SOLO);
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
