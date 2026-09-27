package com.instrumentalsw.backend.infrastructure.ai;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.instrumentalsw.backend.application.TranscriptionArtifactGateway;
import com.instrumentalsw.backend.domain.ArtifactType;
import com.instrumentalsw.backend.domain.RevisionArtifactDescriptor;
import com.instrumentalsw.backend.domain.RevisionArtifactDownload;
import com.instrumentalsw.backend.domain.RevisionArtifactList;
import com.instrumentalsw.backend.domain.TranscriptionException;
import com.instrumentalsw.backend.domain.UploadErrorCode;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import org.springframework.http.HttpHeaders;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

public final class FastApiTranscriptionArtifactClient implements TranscriptionArtifactGateway {
    private static final String LIST_PATH = "/api/v1/transcriptions/{jobId}/revisions/{revisionNumber}/artifacts";
    private static final String DOWNLOAD_PATH = LIST_PATH + "/{artifactId}";
    private final RestClient restClient;
    private final ObjectMapper objectMapper;

    public FastApiTranscriptionArtifactClient(AiServiceProperties properties, ObjectMapper objectMapper) {
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
    public RevisionArtifactList list(UUID jobId, int revisionNumber) {
        return execute(
                () -> restClient.get().uri(LIST_PATH, jobId, revisionNumber).exchange((request, response) -> {
                    byte[] body = readBody(response);
                    requireStatus(response.getStatusCode().value(), 200, body);
                    return parseList(body, jobId, revisionNumber);
                }));
    }

    @Override
    public RevisionArtifactDownload download(UUID jobId, int revisionNumber, String artifactId) {
        RevisionArtifactDescriptor descriptor = list(jobId, revisionNumber).artifacts().stream()
                .filter(candidate -> candidate.artifactId().equals(artifactId))
                .findFirst()
                .orElseThrow(() -> stableError(UploadErrorCode.ARTIFACT_NOT_FOUND));
        return execute(() -> restClient
                .get()
                .uri(DOWNLOAD_PATH, jobId, revisionNumber, artifactId)
                .exchange((request, response) -> {
                    byte[] body = readBody(response);
                    requireStatus(response.getStatusCode().value(), 200, body);
                    validateHeaders(response.getHeaders(), descriptor, body.length);
                    try {
                        return new RevisionArtifactDownload(descriptor, body);
                    } catch (IllegalArgumentException error) {
                        throw serviceError(error);
                    }
                }));
    }

    private RevisionArtifactList parseList(byte[] body, UUID requestedJobId, int requestedRevision) {
        try {
            JsonNode root = objectMapper.readTree(body);
            requireFields(root, Set.of("job_id", "revision_number", "artifacts"));
            UUID jobId = uuid(root, "job_id");
            if (!jobId.equals(requestedJobId)) {
                throw new IllegalArgumentException("upstream job ID mismatch");
            }
            int revisionNumber = integer(root, "revision_number");
            if (revisionNumber != requestedRevision) {
                throw new IllegalArgumentException("upstream revision mismatch");
            }
            JsonNode values = required(root, "artifacts");
            if (!values.isArray()) {
                throw new IllegalArgumentException("artifacts must be an array");
            }
            List<RevisionArtifactDescriptor> descriptors = new ArrayList<>();
            for (JsonNode value : values) {
                requireFields(
                        value,
                        Set.of(
                                "artifact_id",
                                "artifact_type",
                                "filename",
                                "media_type",
                                "extension",
                                "size_bytes",
                                "sha256",
                                "order"));
                descriptors.add(new RevisionArtifactDescriptor(
                        text(value, "artifact_id"),
                        ArtifactType.fromValue(text(value, "artifact_type")),
                        text(value, "filename"),
                        text(value, "media_type"),
                        text(value, "extension"),
                        integer(value, "size_bytes"),
                        text(value, "sha256"),
                        integer(value, "order")));
            }
            return new RevisionArtifactList(jobId, revisionNumber, descriptors);
        } catch (IOException | IllegalArgumentException | NullPointerException error) {
            throw serviceError(error);
        }
    }

    private static void validateHeaders(HttpHeaders headers, RevisionArtifactDescriptor descriptor, int actualLength) {
        String contentType = headers.getFirst(HttpHeaders.CONTENT_TYPE);
        String disposition = headers.getFirst(HttpHeaders.CONTENT_DISPOSITION);
        String contentLength = headers.getFirst(HttpHeaders.CONTENT_LENGTH);
        String contentSha = headers.getFirst("X-Content-SHA256");
        if (!descriptor.mediaType().equals(contentType)) {
            throw serviceError(new IllegalArgumentException("upstream content type mismatch"));
        }
        String expectedDisposition = "attachment; filename=\"" + descriptor.filename() + "\"";
        if (!expectedDisposition.equals(disposition)) {
            throw serviceError(new IllegalArgumentException("upstream disposition mismatch"));
        }
        if (contentLength != null) {
            try {
                if (Long.parseLong(contentLength) != descriptor.sizeBytes()) {
                    throw serviceError(new IllegalArgumentException("upstream content length mismatch"));
                }
            } catch (NumberFormatException error) {
                throw serviceError(error);
            }
        }
        if (actualLength != descriptor.sizeBytes()) {
            throw serviceError(new IllegalArgumentException("upstream body size mismatch"));
        }
        if (!descriptor.sha256().equals(contentSha)) {
            throw serviceError(new IllegalArgumentException("upstream SHA-256 header mismatch"));
        }
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

    private void requireStatus(int actual, int expected, byte[] body) {
        if (actual != expected) {
            throw statusError(actual, body);
        }
    }

    private TranscriptionException statusError(int status, byte[] body) {
        if (status >= 500) {
            return serviceError(new IllegalArgumentException("upstream service failure"));
        }
        try {
            JsonNode root = objectMapper.readTree(body);
            requireFields(root, Set.of("code", "message", "field"));
            UploadErrorCode code = UploadErrorCode.valueOf(text(root, "code"));
            boolean allowed =
                    switch (code) {
                        case INVALID_JOB_ID -> status == 400 || status == 422;
                        case TRANSCRIPTION_NOT_FOUND, REVISION_NOT_FOUND, ARTIFACT_NOT_FOUND -> status == 404;
                        case ARTIFACTS_NOT_READY -> status == 409;
                        default -> false;
                    };
            return allowed
                    ? stableError(code)
                    : serviceError(new IllegalArgumentException("upstream error/status mismatch"));
        } catch (IOException | IllegalArgumentException | NullPointerException error) {
            return serviceError(error);
        }
    }

    private static TranscriptionException stableError(UploadErrorCode code) {
        return switch (code) {
            case INVALID_JOB_ID -> new TranscriptionException(code, "Job ID must be a valid UUID.", "job_id");
            case TRANSCRIPTION_NOT_FOUND -> new TranscriptionException(code, "Transcription job not found.", "job_id");
            case REVISION_NOT_FOUND -> new TranscriptionException(
                    code, "Transcription revision not found.", "revision_number");
            case ARTIFACT_NOT_FOUND -> new TranscriptionException(code, "Revision artifact not found.", "artifact_id");
            case ARTIFACTS_NOT_READY -> new TranscriptionException(
                    code, "Artifacts are not available for this revision yet.", "revision_number");
            default -> serviceError(new IllegalArgumentException("unsupported artifact error"));
        };
    }

    private static TranscriptionException unavailable(Throwable cause) {
        return new TranscriptionException(
                UploadErrorCode.AI_SERVICE_UNAVAILABLE, "The AI service is unavailable.", null, cause);
    }

    private static TranscriptionException serviceError(Throwable cause) {
        return new TranscriptionException(
                UploadErrorCode.AI_SERVICE_ERROR, "The AI service returned an invalid response.", null, cause);
    }

    private static byte[] readBody(ClientHttpResponse response) {
        try {
            return response.getBody().readAllBytes();
        } catch (IOException error) {
            throw serviceError(error);
        }
    }

    private static void requireFields(JsonNode node, Set<String> expected) {
        if (node == null || !node.isObject()) {
            throw new IllegalArgumentException("payload must be an object");
        }
        Set<String> actual = new HashSet<>();
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

    private static UUID uuid(JsonNode parent, String field) {
        return UUID.fromString(text(parent, field));
    }

    @FunctionalInterface
    private interface HttpCall<T> {
        T run();
    }
}
