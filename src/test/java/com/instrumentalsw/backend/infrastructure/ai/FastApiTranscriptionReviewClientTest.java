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
import java.util.concurrent.Executors;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class FastApiTranscriptionReviewClientTest {
    private static final UUID JOB_ID = UUID.fromString("11111111-1111-1111-1111-111111111111");
    private HttpServer server;

    @AfterEach
    void stopServer() {
        if (server != null) {
            server.stop(0);
        }
    }

    @Test
    void forwardsExactBodylessGetAndParsesCompleteReview() throws Exception {
        RecordedRequest recorded = new RecordedRequest();
        start(exchange -> {
            recorded.method = exchange.getRequestMethod();
            recorded.path = exchange.getRequestURI().getRawPath();
            recorded.body = exchange.getRequestBody().readAllBytes();
            respond(exchange, 200, validJson());
        });

        var result = client().get(JOB_ID);

        assertThat(recorded.method).isEqualTo("GET");
        assertThat(recorded.path).isEqualTo("/api/v1/transcriptions/" + JOB_ID + "/review");
        assertThat(recorded.body).isEmpty();
        assertThat(result.jobId()).isEqualTo(JOB_ID);
        assertThat(result.summary().eventCount()).isEqualTo(2);
        assertThat(result.summary().lowConfidenceCount()).isEqualTo(1);
        assertThat(result.events()).hasSize(2);
        assertThat(result.events().get(0).writtenPitchMidi()).isEqualTo(69);
        assertThat(result.events().get(0).pitchConcertMidi()).isEqualTo(60);
        assertThat(result.events().get(0).isLowConfidence()).isTrue();
    }

    @ParameterizedTest
    @CsvSource({
        "404,TRANSCRIPTION_NOT_FOUND,404",
        "409,TRANSCRIPTION_RESULT_NOT_READY,409",
        "422,INVALID_JOB_ID,400",
        "500,AI_SERVICE_ERROR,502",
        "503,AI_SERVICE_ERROR,502"
    })
    void mapsUpstreamStatusesWithoutLeakingBody(int status, UploadErrorCode code, int publicStatus) throws Exception {
        start(exchange -> respond(exchange, status, "<html>private localhost:8000</html>"));

        assertThatThrownBy(() -> client().get(JOB_ID))
                .isInstanceOf(TranscriptionException.class)
                .satisfies(error -> {
                    var controlled = (TranscriptionException) error;
                    assertThat(controlled.code()).isEqualTo(code);
                    assertThat(controlled.publicStatus()).isEqualTo(publicStatus);
                    assertThat(controlled.getMessage()).doesNotContain("localhost", "<html>");
                });
    }

    @Test
    void mapsTimeoutAndRefusalToUnavailable() throws Exception {
        start(exchange -> {
            try {
                Thread.sleep(300);
                respond(exchange, 200, validJson());
            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();
            }
        });
        assertCode(UploadErrorCode.AI_SERVICE_UNAVAILABLE, () -> client(Duration.ofMillis(50))
                .get(JOB_ID));
        server.stop(0);
        server = null;

        int port;
        try (ServerSocket socket = new ServerSocket(0)) {
            port = socket.getLocalPort();
        }
        var refused = new FastApiTranscriptionReviewClient(
                new AiServiceProperties("http://127.0.0.1:" + port, Duration.ofMillis(100), Duration.ofMillis(100)),
                new ObjectMapper());
        assertCode(UploadErrorCode.AI_SERVICE_UNAVAILABLE, () -> refused.get(JOB_ID));
    }

    @ParameterizedTest
    @CsvSource({
        "malformed,{not-json",
        "uuid,REPLACE_UUID",
        "version,REPLACE_VERSION",
        "indices,REPLACE_INDEX",
        "counts,REPLACE_COUNT",
        "event,REPLACE_EVENT"
    })
    void rejectsIncompatibleHttp200(String name, String replacement) throws Exception {
        String body =
                switch (replacement) {
                    case "REPLACE_UUID" -> validJson()
                            .replace(JOB_ID.toString(), "22222222-2222-2222-2222-222222222222");
                    case "REPLACE_VERSION" -> validJson().replaceFirst("\\\"1.0\\\"", "\"2.0\"");
                    case "REPLACE_INDEX" -> validJson().replace("\"index\":1", "\"index\":3");
                    case "REPLACE_COUNT" -> validJson().replace("\"event_count\":2", "\"event_count\":9");
                    case "REPLACE_EVENT" -> validJson().replace("\"confidence\":0.42", "\"confidence\":2.0");
                    default -> replacement;
                };
        start(exchange -> respond(exchange, 200, body));
        assertCode(UploadErrorCode.AI_SERVICE_ERROR, () -> client().get(JOB_ID));
        assertThat(name).isNotBlank();
    }

    private FastApiTranscriptionReviewClient client() {
        return client(Duration.ofSeconds(1));
    }

    private FastApiTranscriptionReviewClient client(Duration timeout) {
        return new FastApiTranscriptionReviewClient(
                new AiServiceProperties(baseUrl(), timeout, timeout), new ObjectMapper());
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

    private static void assertCode(UploadErrorCode code, ThrowingCall call) {
        assertThatThrownBy(call::run).isInstanceOf(TranscriptionException.class).satisfies(error -> assertThat(
                        ((TranscriptionException) error).code())
                .isEqualTo(code));
    }

    private static String validJson() {
        return """
                {
                  "job_id":"11111111-1111-1111-1111-111111111111",
                  "schema_version":"1.0",
                  "note_event_schema_version":"1.0",
                  "low_confidence_policy_version":"1.0",
                  "written_pitch_policy_version":"1.0",
                  "saxophone_type":"alto",
                  "low_confidence_threshold":0.5,
                  "confidence_interpretation":"model_signal_not_calibrated_accuracy",
                  "confidence_method":"model_probability",
                  "summary":{"event_count":2,"low_confidence_count":1},
                  "events":[
                    {
                      "index":0,"pitch_concert_midi":60,"written_pitch_midi":69,
                      "onset_seconds":0.0,"offset_seconds":0.5,"velocity":90,
                      "confidence":0.42,"is_low_confidence":true
                    },
                    {
                      "index":1,"pitch_concert_midi":67,"written_pitch_midi":76,
                      "onset_seconds":0.25,"offset_seconds":1.0,"velocity":100,
                      "confidence":0.82,"is_low_confidence":false
                    }
                  ]
                }
                """;
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
        private byte[] body;
    }
}
