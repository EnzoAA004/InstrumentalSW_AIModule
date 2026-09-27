package com.instrumentalsw.backend.infrastructure.ai;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.instrumentalsw.backend.application.RevisionAddOperation;
import com.instrumentalsw.backend.application.RevisionCreateCommand;
import com.instrumentalsw.backend.application.RevisionDeleteOperation;
import com.instrumentalsw.backend.application.RevisionUpdateOperation;
import com.instrumentalsw.backend.domain.TranscriptionException;
import com.instrumentalsw.backend.domain.UploadErrorCode;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.Executors;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class FastApiTranscriptionRevisionClientTest {
    private static final UUID JOB_ID = UUID.fromString("11111111-1111-1111-1111-111111111111");
    private static final String REVISIONS_PATH =
            "/api/v1/transcriptions/11111111-1111-1111-1111-111111111111/revisions";
    private static final String DETAIL_PATH = REVISIONS_PATH + "/1";
    private static final String REGENERATION_PATH = DETAIL_PATH + "/regeneration-requests";
    private static final String GET_HISTORY = "GET:" + REVISIONS_PATH;
    private static final String GET_DETAIL = "GET:" + DETAIL_PATH;
    private static final String POST_REVISION = "POST:" + REVISIONS_PATH;
    private static final String POST_REGENERATION = "POST:" + REGENERATION_PATH;

    private final ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();
    private HttpServer server;

    @AfterEach
    void stopServer() {
        if (server != null) {
            server.stop(0);
        }
    }

    @Test
    void forwardsExactMethodsPathsAndRevisionJson() throws Exception {
        RecordedRequest historyRequest = new RecordedRequest();
        RecordedRequest detailRequest = new RecordedRequest();
        RecordedRequest createRequest = new RecordedRequest();
        RecordedRequest regenerationRequest = new RecordedRequest();
        start(exchange -> {
            RecordedRequest target =
                    switch (exchange.getRequestURI().getPath()) {
                        case REVISIONS_PATH -> exchange.getRequestMethod().equals("GET")
                                ? historyRequest
                                : createRequest;
                        case DETAIL_PATH -> detailRequest;
                        case REGENERATION_PATH -> regenerationRequest;
                        default -> throw new IOException("unexpected path");
                    };
            target.capture(exchange);
            String body =
                    switch (target.kind()) {
                        case GET_HISTORY -> historyJson();
                        case GET_DETAIL, POST_REVISION -> revisionJson();
                        case POST_REGENERATION -> regenerationJson();
                        default -> throw new IOException("unexpected request");
                    };
            int status = target == regenerationRequest ? 202 : target == createRequest ? 201 : 200;
            respond(exchange, status, body);
        });
        var client = client(Duration.ofSeconds(1));
        var command = new RevisionCreateCommand(
                0,
                List.of(
                        new RevisionUpdateOperation("source-0", 70, 0.1, 0.6),
                        new RevisionAddOperation(72, 0.7, 1.0, 64),
                        new RevisionDeleteOperation("source-1")));

        assertThat(client.history(JOB_ID).revisionCount()).isEqualTo(2);
        assertThat(client.get(JOB_ID, 1).events()).hasSize(2);
        assertThat(client.create(JOB_ID, command).revisionNumber()).isEqualTo(1);
        assertThat(client.requestRegeneration(JOB_ID, 1).requestedArtifacts())
                .containsExactly("midi", "musicxml", "svg");

        assertThat(historyRequest.kind()).isEqualTo(GET_HISTORY);
        assertThat(historyRequest.body).isEmpty();
        assertThat(detailRequest.kind()).isEqualTo(GET_DETAIL);
        assertThat(detailRequest.body).isEmpty();
        assertThat(createRequest.kind()).isEqualTo(POST_REVISION);
        JsonNode sent = objectMapper.readTree(createRequest.body);
        assertThat(sent)
                .isEqualTo(
                        objectMapper.readTree(
                                """
                        {
                          "base_revision_number": 0,
                          "operations": [
                            {
                              "type": "update",
                              "event_id": "source-0",
                              "written_pitch_midi": 70,
                              "onset_seconds": 0.1,
                              "offset_seconds": 0.6
                            },
                            {
                              "type": "add",
                              "written_pitch_midi": 72,
                              "onset_seconds": 0.7,
                              "offset_seconds": 1.0,
                              "velocity": 64
                            },
                            {
                              "type": "delete",
                              "event_id": "source-1"
                            }
                          ]
                        }
                        """));
        assertThat(regenerationRequest.kind()).isEqualTo(POST_REGENERATION);
        assertThat(regenerationRequest.body).isEmpty();
    }

    @ParameterizedTest
    @CsvSource({
        "400,INVALID_JOB_ID,400",
        "404,TRANSCRIPTION_NOT_FOUND,404",
        "404,REVISION_NOT_FOUND,404",
        "409,TRANSCRIPTION_RESULT_NOT_READY,409",
        "409,REVISION_CONFLICT,409",
        "422,INVALID_REVISION_OPERATION,422",
        "422,INVALID_REVISION_EVENT,422",
        "500,AI_SERVICE_ERROR,502",
        "503,AI_SERVICE_ERROR,502"
    })
    void mapsStableUpstreamErrors(int status, UploadErrorCode code, int publicStatus) throws Exception {
        start(exchange ->
                respond(exchange, status, "{\"code\":\"" + code + "\",\"message\":\"safe\",\"field\":\"operations\"}"));
        assertThatThrownBy(() -> client(Duration.ofSeconds(1)).history(JOB_ID))
                .isInstanceOf(TranscriptionException.class)
                .satisfies(error -> {
                    var controlled = (TranscriptionException) error;
                    assertThat(controlled.code()).isEqualTo(code);
                    assertThat(controlled.publicStatus()).isEqualTo(publicStatus);
                    assertThat(controlled.getMessage()).doesNotContain("localhost", "<html>");
                });
    }

    @Test
    void rejectsMalformedAndInconsistentSuccessPayloads() throws Exception {
        start(exchange ->
                respond(exchange, 200, revisionJson().replace("\"job_id\": \"11111111", "\"job_id\": \"22222222")));
        assertCode(UploadErrorCode.AI_SERVICE_ERROR, () -> client(Duration.ofSeconds(1))
                .get(JOB_ID, 1));
        server.stop(0);
        server = null;

        start(exchange -> respond(exchange, 200, "{not-json"));
        assertCode(UploadErrorCode.AI_SERVICE_ERROR, () -> client(Duration.ofSeconds(1))
                .history(JOB_ID));
    }

    @Test
    void mapsTimeoutAndRefusalWithoutRetry() throws Exception {
        start(exchange -> {
            try {
                Thread.sleep(300);
                respond(exchange, 200, historyJson());
            } catch (InterruptedException error) {
                Thread.currentThread().interrupt();
            }
        });
        assertCode(UploadErrorCode.AI_SERVICE_UNAVAILABLE, () -> client(Duration.ofMillis(50))
                .history(JOB_ID));
        server.stop(0);
        server = null;

        int port;
        try (ServerSocket socket = new ServerSocket(0)) {
            port = socket.getLocalPort();
        }
        var properties =
                new AiServiceProperties("http://127.0.0.1:" + port, Duration.ofMillis(100), Duration.ofMillis(100));
        var refused = new FastApiTranscriptionRevisionClient(properties, objectMapper);
        assertCode(UploadErrorCode.AI_SERVICE_UNAVAILABLE, () -> refused.history(JOB_ID));
    }

    private FastApiTranscriptionRevisionClient client(Duration timeout) {
        return new FastApiTranscriptionRevisionClient(
                new AiServiceProperties(baseUrl(), timeout, timeout), objectMapper);
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

    private static String historyJson() {
        return """
                {
                  "job_id": "11111111-1111-1111-1111-111111111111",
                  "latest_revision_number": 1,
                  "revision_count": 2,
                  "revisions": [
                    {
                      "revision_number": 0,
                      "parent_revision_number": null,
                      "created_at": "2026-07-22T11:00:00Z",
                      "event_count": 2,
                      "model_event_count": 2,
                      "human_event_count": 0,
                      "derived_artifacts_status": "CURRENT"
                    },
                    {
                      "revision_number": 1,
                      "parent_revision_number": 0,
                      "created_at": "2026-07-22T12:00:00Z",
                      "event_count": 2,
                      "model_event_count": 1,
                      "human_event_count": 1,
                      "derived_artifacts_status": "STALE"
                    }
                  ]
                }
                """;
    }

    private static String revisionJson() {
        return """
                {
                  "job_id": "11111111-1111-1111-1111-111111111111",
                  "revision_number": 1,
                  "parent_revision_number": 0,
                  "created_at": "2026-07-22T12:00:00Z",
                  "saxophone_type": "alto",
                  "events": [
                    {
                      "event_id": "source-0",
                      "origin": "model",
                      "source_index": 0,
                      "pitch_concert_midi": 61,
                      "written_pitch_midi": 70,
                      "onset_seconds": 0.1,
                      "offset_seconds": 0.6,
                      "velocity": 90,
                      "confidence": 0.42,
                      "is_low_confidence": true
                    },
                    {
                      "event_id": "human-22222222-2222-2222-2222-222222222222",
                      "origin": "human",
                      "source_index": null,
                      "pitch_concert_midi": 63,
                      "written_pitch_midi": 72,
                      "onset_seconds": 0.7,
                      "offset_seconds": 1.0,
                      "velocity": 64,
                      "confidence": null,
                      "is_low_confidence": null
                    }
                  ],
                  "summary": {
                    "event_count": 2,
                    "model_event_count": 1,
                    "human_event_count": 1
                  },
                  "derived_artifacts_status": "STALE",
                  "schema_version": "1.0"
                }
                """;
    }

    private static String regenerationJson() {
        return """
                {
                  "request_id": "33333333-3333-3333-3333-333333333333",
                  "job_id": "11111111-1111-1111-1111-111111111111",
                  "revision_number": 1,
                  "status": "REQUESTED",
                  "requested_artifacts": ["midi", "musicxml", "svg"]
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
        private byte[] body = new byte[0];

        private void capture(HttpExchange exchange) throws IOException {
            method = exchange.getRequestMethod();
            path = exchange.getRequestURI().getRawPath();
            body = exchange.getRequestBody().readAllBytes();
        }

        private String kind() {
            return method + ":" + path;
        }
    }
}
