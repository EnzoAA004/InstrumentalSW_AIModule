package com.instrumentalsw.backend.infrastructure.ai;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.instrumentalsw.backend.application.TranscriptionReviewGateway;
import com.instrumentalsw.backend.domain.SaxophoneType;
import com.instrumentalsw.backend.domain.TranscriptionException;
import com.instrumentalsw.backend.domain.TranscriptionReview;
import com.instrumentalsw.backend.domain.TranscriptionReviewEvent;
import com.instrumentalsw.backend.domain.TranscriptionReviewSummary;
import com.instrumentalsw.backend.domain.UploadErrorCode;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

public final class FastApiTranscriptionReviewClient implements TranscriptionReviewGateway {
    private static final String PATH = "/api/v1/transcriptions/{jobId}/review";
    private final RestClient restClient;
    private final ObjectMapper objectMapper;

    public FastApiTranscriptionReviewClient(AiServiceProperties properties, ObjectMapper objectMapper) {
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
    public TranscriptionReview get(UUID jobId) {
        try {
            return restClient.get().uri(PATH, jobId).exchange((request, response) -> {
                int status = response.getStatusCode().value();
                byte[] body = readBody(response);
                if (status != 200) {
                    throw statusError(status);
                }
                return parse(body, jobId);
            });
        } catch (TranscriptionException error) {
            throw error;
        } catch (ResourceAccessException error) {
            throw unavailable(error);
        } catch (RuntimeException error) {
            throw serviceError(error);
        }
    }

    private TranscriptionReview parse(byte[] body, UUID requestedJobId) {
        try {
            JsonNode root = objectMapper.readTree(body);
            UUID jobId = UUID.fromString(text(root, "job_id"));
            if (!jobId.equals(requestedJobId)) {
                throw new IllegalArgumentException("upstream job ID mismatch");
            }
            JsonNode summaryNode = object(root, "summary");
            TranscriptionReviewSummary summary = new TranscriptionReviewSummary(
                    integer(summaryNode, "event_count"), integer(summaryNode, "low_confidence_count"));
            JsonNode eventsNode = required(root, "events");
            if (!eventsNode.isArray()) {
                throw new IllegalArgumentException("events must be an array");
            }
            List<TranscriptionReviewEvent> events = new ArrayList<>();
            for (JsonNode event : eventsNode) {
                if (!event.isObject()) {
                    throw new IllegalArgumentException("event must be an object");
                }
                events.add(new TranscriptionReviewEvent(
                        integer(event, "index"),
                        integer(event, "pitch_concert_midi"),
                        integer(event, "written_pitch_midi"),
                        number(event, "onset_seconds"),
                        number(event, "offset_seconds"),
                        integer(event, "velocity"),
                        number(event, "confidence"),
                        bool(event, "is_low_confidence")));
            }
            return new TranscriptionReview(
                    jobId,
                    text(root, "schema_version"),
                    text(root, "note_event_schema_version"),
                    text(root, "low_confidence_policy_version"),
                    text(root, "written_pitch_policy_version"),
                    SaxophoneType.fromValue(text(root, "saxophone_type")),
                    number(root, "low_confidence_threshold"),
                    text(root, "confidence_interpretation"),
                    text(root, "confidence_method"),
                    summary,
                    events);
        } catch (TranscriptionException error) {
            throw serviceError(error);
        } catch (IOException | IllegalArgumentException | NullPointerException error) {
            throw serviceError(error);
        }
    }

    private static JsonNode required(JsonNode parent, String field) {
        if (parent == null || !parent.isObject()) {
            throw new IllegalArgumentException("payload must be an object");
        }
        JsonNode value = parent.get(field);
        if (value == null || value.isNull()) {
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

    private static double number(JsonNode parent, String field) {
        JsonNode value = required(parent, field);
        if (!value.isNumber() || !Double.isFinite(value.doubleValue())) {
            throw new IllegalArgumentException(field + " must be a finite number");
        }
        return value.doubleValue();
    }

    private static boolean bool(JsonNode parent, String field) {
        JsonNode value = required(parent, field);
        if (!value.isBoolean()) {
            throw new IllegalArgumentException(field + " must be a boolean");
        }
        return value.booleanValue();
    }

    private static byte[] readBody(ClientHttpResponse response) {
        try {
            return response.getBody().readAllBytes();
        } catch (IOException error) {
            throw serviceError(error);
        }
    }

    private static TranscriptionException statusError(int status) {
        return switch (status) {
            case 404 -> new TranscriptionException(
                    UploadErrorCode.TRANSCRIPTION_NOT_FOUND, "Transcription job not found.", "job_id");
            case 409 -> new TranscriptionException(
                    UploadErrorCode.TRANSCRIPTION_RESULT_NOT_READY,
                    "Transcription notes are not available yet.",
                    "job_id");
            case 422 -> new TranscriptionException(
                    UploadErrorCode.INVALID_JOB_ID, "Job ID must be a valid UUID.", "job_id");
            default -> serviceError(new IllegalStateException("unexpected upstream review status"));
        };
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
}
