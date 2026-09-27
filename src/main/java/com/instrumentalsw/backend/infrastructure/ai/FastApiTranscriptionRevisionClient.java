package com.instrumentalsw.backend.infrastructure.ai;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.instrumentalsw.backend.application.RevisionAddOperation;
import com.instrumentalsw.backend.application.RevisionCreateCommand;
import com.instrumentalsw.backend.application.RevisionDeleteOperation;
import com.instrumentalsw.backend.application.RevisionOperation;
import com.instrumentalsw.backend.application.RevisionUpdateOperation;
import com.instrumentalsw.backend.application.TranscriptionRevisionGateway;
import com.instrumentalsw.backend.domain.DerivedArtifactsStatus;
import com.instrumentalsw.backend.domain.EventOrigin;
import com.instrumentalsw.backend.domain.RegenerationRequest;
import com.instrumentalsw.backend.domain.RegenerationRequestStatus;
import com.instrumentalsw.backend.domain.SaxophoneType;
import com.instrumentalsw.backend.domain.TranscriptionException;
import com.instrumentalsw.backend.domain.TranscriptionRevision;
import com.instrumentalsw.backend.domain.TranscriptionRevisionEvent;
import com.instrumentalsw.backend.domain.TranscriptionRevisionHistory;
import com.instrumentalsw.backend.domain.TranscriptionRevisionHistoryEntry;
import com.instrumentalsw.backend.domain.TranscriptionRevisionSummary;
import com.instrumentalsw.backend.domain.UploadErrorCode;
import java.io.IOException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import org.springframework.http.MediaType;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

public final class FastApiTranscriptionRevisionClient implements TranscriptionRevisionGateway {
    private static final String REVISIONS_PATH = "/api/v1/transcriptions/{jobId}/revisions";
    private static final String REVISION_PATH = REVISIONS_PATH + "/{revisionNumber}";
    private static final String REGENERATION_PATH = REVISION_PATH + "/regeneration-requests";
    private final RestClient restClient;
    private final ObjectMapper objectMapper;

    public FastApiTranscriptionRevisionClient(AiServiceProperties properties, ObjectMapper objectMapper) {
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(properties.connectTimeout());
        requestFactory.setReadTimeout(properties.readTimeout());
        this.restClient = RestClient.builder()
                .baseUrl(properties.baseUrl())
                .requestFactory(requestFactory)
                .build();
        this.objectMapper = objectMapper;
    }

    @Override
    public TranscriptionRevisionHistory history(UUID jobId) {
        return execute(() -> restClient.get().uri(REVISIONS_PATH, jobId).exchange((request, response) -> {
            byte[] body = readBody(response);
            requireStatus(response.getStatusCode().value(), 200, body);
            return parseHistory(body, jobId);
        }));
    }

    @Override
    public TranscriptionRevision get(UUID jobId, int revisionNumber) {
        return execute(
                () -> restClient.get().uri(REVISION_PATH, jobId, revisionNumber).exchange((request, response) -> {
                    byte[] body = readBody(response);
                    requireStatus(response.getStatusCode().value(), 200, body);
                    return parseRevision(body, jobId, revisionNumber);
                }));
    }

    @Override
    public TranscriptionRevision create(UUID jobId, RevisionCreateCommand command) {
        Map<String, Object> body = commandBody(command);
        return execute(() -> restClient
                .post()
                .uri(REVISIONS_PATH, jobId)
                .contentType(MediaType.APPLICATION_JSON)
                .body(body)
                .exchange((request, response) -> {
                    byte[] responseBody = readBody(response);
                    requireStatus(response.getStatusCode().value(), 201, responseBody);
                    return parseRevision(responseBody, jobId, command.baseRevisionNumber() + 1);
                }));
    }

    @Override
    public RegenerationRequest requestRegeneration(UUID jobId, int revisionNumber) {
        return execute(() -> restClient
                .post()
                .uri(REGENERATION_PATH, jobId, revisionNumber)
                .exchange((request, response) -> {
                    byte[] body = readBody(response);
                    requireStatus(response.getStatusCode().value(), 202, body);
                    return parseRegenerationRequest(body, jobId, revisionNumber);
                }));
    }

    private <T> T execute(HttpCall<T> call) {
        try {
            return call.run();
        } catch (TranscriptionException error) {
            throw error;
        } catch (ResourceAccessException error) {
            throw unavailable(error);
        } catch (RuntimeException error) {
            throw serviceError(error);
        }
    }

    private TranscriptionRevisionHistory parseHistory(byte[] body, UUID requestedJobId) {
        try {
            JsonNode root = objectMapper.readTree(body);
            requireFields(root, Set.of("job_id", "latest_revision_number", "revision_count", "revisions"));
            UUID jobId = uuid(root, "job_id");
            requireIdentity(jobId, requestedJobId);
            JsonNode revisionsNode = array(root, "revisions");
            List<TranscriptionRevisionHistoryEntry> entries = new ArrayList<>();
            for (JsonNode node : revisionsNode) {
                requireFields(
                        node,
                        Set.of(
                                "revision_number",
                                "parent_revision_number",
                                "created_at",
                                "event_count",
                                "model_event_count",
                                "human_event_count",
                                "derived_artifacts_status"));
                entries.add(new TranscriptionRevisionHistoryEntry(
                        integer(node, "revision_number"),
                        nullableInteger(node, "parent_revision_number"),
                        instant(node, "created_at"),
                        integer(node, "event_count"),
                        integer(node, "model_event_count"),
                        integer(node, "human_event_count"),
                        DerivedArtifactsStatus.valueOf(text(node, "derived_artifacts_status"))));
            }
            return new TranscriptionRevisionHistory(
                    jobId, integer(root, "latest_revision_number"), integer(root, "revision_count"), entries);
        } catch (IOException | IllegalArgumentException | NullPointerException error) {
            throw serviceError(error);
        }
    }

    private TranscriptionRevision parseRevision(byte[] body, UUID requestedJobId, int requestedRevisionNumber) {
        try {
            JsonNode root = objectMapper.readTree(body);
            requireFields(
                    root,
                    Set.of(
                            "job_id",
                            "revision_number",
                            "parent_revision_number",
                            "created_at",
                            "saxophone_type",
                            "events",
                            "summary",
                            "derived_artifacts_status",
                            "schema_version"));
            UUID jobId = uuid(root, "job_id");
            requireIdentity(jobId, requestedJobId);
            int revisionNumber = integer(root, "revision_number");
            if (revisionNumber != requestedRevisionNumber) {
                throw new IllegalArgumentException("upstream revision number mismatch");
            }
            JsonNode eventsNode = array(root, "events");
            List<TranscriptionRevisionEvent> events = new ArrayList<>();
            for (JsonNode event : eventsNode) {
                requireFields(
                        event,
                        Set.of(
                                "event_id",
                                "origin",
                                "source_index",
                                "pitch_concert_midi",
                                "written_pitch_midi",
                                "onset_seconds",
                                "offset_seconds",
                                "velocity",
                                "confidence",
                                "is_low_confidence"));
                events.add(new TranscriptionRevisionEvent(
                        text(event, "event_id"),
                        EventOrigin.fromValue(text(event, "origin")),
                        nullableInteger(event, "source_index"),
                        integer(event, "pitch_concert_midi"),
                        integer(event, "written_pitch_midi"),
                        number(event, "onset_seconds"),
                        number(event, "offset_seconds"),
                        integer(event, "velocity"),
                        nullableNumber(event, "confidence"),
                        nullableBoolean(event, "is_low_confidence")));
            }
            JsonNode summaryNode = object(root, "summary");
            requireFields(summaryNode, Set.of("event_count", "model_event_count", "human_event_count"));
            return new TranscriptionRevision(
                    jobId,
                    revisionNumber,
                    nullableInteger(root, "parent_revision_number"),
                    instant(root, "created_at"),
                    SaxophoneType.fromValue(text(root, "saxophone_type")),
                    events,
                    new TranscriptionRevisionSummary(
                            integer(summaryNode, "event_count"),
                            integer(summaryNode, "model_event_count"),
                            integer(summaryNode, "human_event_count")),
                    DerivedArtifactsStatus.valueOf(text(root, "derived_artifacts_status")),
                    text(root, "schema_version"));
        } catch (IOException | IllegalArgumentException | NullPointerException error) {
            throw serviceError(error);
        }
    }

    private RegenerationRequest parseRegenerationRequest(
            byte[] body, UUID requestedJobId, int requestedRevisionNumber) {
        try {
            JsonNode root = objectMapper.readTree(body);
            requireFields(root, Set.of("request_id", "job_id", "revision_number", "status", "requested_artifacts"));
            UUID jobId = uuid(root, "job_id");
            requireIdentity(jobId, requestedJobId);
            int revisionNumber = integer(root, "revision_number");
            if (revisionNumber != requestedRevisionNumber) {
                throw new IllegalArgumentException("upstream revision number mismatch");
            }
            List<String> artifacts = new ArrayList<>();
            for (JsonNode artifact : array(root, "requested_artifacts")) {
                if (!artifact.isTextual()) {
                    throw new IllegalArgumentException("requested artifact must be text");
                }
                artifacts.add(artifact.textValue());
            }
            return new RegenerationRequest(
                    uuid(root, "request_id"),
                    jobId,
                    revisionNumber,
                    RegenerationRequestStatus.valueOf(text(root, "status")),
                    artifacts);
        } catch (IOException | IllegalArgumentException | NullPointerException error) {
            throw serviceError(error);
        }
    }

    private static Map<String, Object> commandBody(RevisionCreateCommand command) {
        Map<String, Object> root = new LinkedHashMap<>();
        root.put("base_revision_number", command.baseRevisionNumber());
        List<Map<String, Object>> operations = new ArrayList<>();
        for (RevisionOperation operation : command.operations()) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("type", operation.type());
            if (operation instanceof RevisionUpdateOperation update) {
                item.put("event_id", update.eventId());
                item.put("written_pitch_midi", update.writtenPitchMidi());
                item.put("onset_seconds", update.onsetSeconds());
                item.put("offset_seconds", update.offsetSeconds());
            } else if (operation instanceof RevisionAddOperation add) {
                item.put("written_pitch_midi", add.writtenPitchMidi());
                item.put("onset_seconds", add.onsetSeconds());
                item.put("offset_seconds", add.offsetSeconds());
                item.put("velocity", add.velocity());
            } else if (operation instanceof RevisionDeleteOperation delete) {
                item.put("event_id", delete.eventId());
            }
            operations.add(item);
        }
        root.put("operations", operations);
        return root;
    }

    private void requireStatus(int actual, int expected, byte[] body) {
        if (actual != expected) {
            throw statusError(actual, body);
        }
    }

    private TranscriptionException statusError(int status, byte[] body) {
        try {
            JsonNode root = objectMapper.readTree(body);
            requireFields(root, Set.of("code", "message", "field"));
            UploadErrorCode code = UploadErrorCode.valueOf(text(root, "code"));
            if (!isAllowedStatus(code, status)) {
                return serviceError(new IllegalArgumentException("upstream error/status mismatch"));
            }
            return stableError(code);
        } catch (IOException | IllegalArgumentException | NullPointerException error) {
            return serviceError(error);
        }
    }

    private static boolean isAllowedStatus(UploadErrorCode code, int status) {
        return switch (code) {
            case INVALID_JOB_ID -> status == 400 || status == 422;
            case TRANSCRIPTION_NOT_FOUND, REVISION_NOT_FOUND -> status == 404;
            case TRANSCRIPTION_RESULT_NOT_READY, REVISION_CONFLICT -> status == 409;
            case INVALID_REVISION_OPERATION, INVALID_REVISION_EVENT -> status == 422;
            default -> false;
        };
    }

    private static TranscriptionException stableError(UploadErrorCode code) {
        return switch (code) {
            case INVALID_JOB_ID -> new TranscriptionException(code, "Job ID must be a valid UUID.", "job_id");
            case TRANSCRIPTION_NOT_FOUND -> new TranscriptionException(code, "Transcription job not found.", "job_id");
            case TRANSCRIPTION_RESULT_NOT_READY -> new TranscriptionException(
                    code, "Transcription notes are not available yet.", "job_id");
            case REVISION_NOT_FOUND -> new TranscriptionException(
                    code, "Transcription revision not found.", "revision_number");
            case REVISION_CONFLICT -> new TranscriptionException(
                    code, "The transcription revision has changed.", "base_revision_number");
            case INVALID_REVISION_OPERATION -> new TranscriptionException(
                    code, "The revision operation is invalid.", "operations");
            case INVALID_REVISION_EVENT -> new TranscriptionException(
                    code, "The revision event is invalid.", "operations");
            default -> serviceError(new IllegalArgumentException("unsupported upstream error"));
        };
    }

    private static void requireIdentity(UUID actual, UUID requested) {
        if (!actual.equals(requested)) {
            throw new IllegalArgumentException("upstream job ID mismatch");
        }
    }

    private static void requireFields(JsonNode node, Set<String> expected) {
        if (node == null || !node.isObject()) {
            throw new IllegalArgumentException("payload must be an object");
        }
        Set<String> actual = new java.util.HashSet<>();
        node.fieldNames().forEachRemaining(actual::add);
        if (!actual.equals(expected)) {
            throw new IllegalArgumentException("payload fields are incompatible");
        }
    }

    private static JsonNode required(JsonNode parent, String field) {
        JsonNode value = parent.get(field);
        if (value == null) {
            throw new IllegalArgumentException(field + " is required");
        }
        return value;
    }

    private static JsonNode object(JsonNode parent, String field) {
        JsonNode value = required(parent, field);
        if (!value.isObject()) {
            throw new IllegalArgumentException(field + " must be an object");
        }
        return value;
    }

    private static JsonNode array(JsonNode parent, String field) {
        JsonNode value = required(parent, field);
        if (!value.isArray()) {
            throw new IllegalArgumentException(field + " must be an array");
        }
        return value;
    }

    private static String text(JsonNode parent, String field) {
        JsonNode value = required(parent, field);
        if (!value.isTextual() || value.textValue().isBlank()) {
            throw new IllegalArgumentException(field + " must be non-blank text");
        }
        return value.textValue();
    }

    private static int integer(JsonNode parent, String field) {
        JsonNode value = required(parent, field);
        if (!value.isIntegralNumber() || !value.canConvertToInt()) {
            throw new IllegalArgumentException(field + " must be an integer");
        }
        return value.intValue();
    }

    private static Integer nullableInteger(JsonNode parent, String field) {
        JsonNode value = required(parent, field);
        return value.isNull() ? null : integer(parent, field);
    }

    private static double number(JsonNode parent, String field) {
        JsonNode value = required(parent, field);
        if (!value.isNumber() || !Double.isFinite(value.doubleValue())) {
            throw new IllegalArgumentException(field + " must be a finite number");
        }
        return value.doubleValue();
    }

    private static Double nullableNumber(JsonNode parent, String field) {
        JsonNode value = required(parent, field);
        return value.isNull() ? null : number(parent, field);
    }

    private static Boolean nullableBoolean(JsonNode parent, String field) {
        JsonNode value = required(parent, field);
        if (value.isNull()) {
            return null;
        }
        if (!value.isBoolean()) {
            throw new IllegalArgumentException(field + " must be a boolean or null");
        }
        return value.booleanValue();
    }

    private static UUID uuid(JsonNode parent, String field) {
        return UUID.fromString(text(parent, field));
    }

    private static Instant instant(JsonNode parent, String field) {
        return Instant.parse(text(parent, field));
    }

    private static byte[] readBody(ClientHttpResponse response) {
        try {
            return response.getBody().readAllBytes();
        } catch (IOException error) {
            throw serviceError(error);
        }
    }

    private static TranscriptionException unavailable(Throwable cause) {
        return new TranscriptionException(
                UploadErrorCode.AI_SERVICE_UNAVAILABLE, "The transcription service is unavailable.", null, cause);
    }

    private static TranscriptionException serviceError(Throwable cause) {
        return new TranscriptionException(
                UploadErrorCode.AI_SERVICE_ERROR,
                "The transcription service returned an invalid response.",
                null,
                cause);
    }

    @FunctionalInterface
    private interface HttpCall<T> {
        T run();
    }
}
