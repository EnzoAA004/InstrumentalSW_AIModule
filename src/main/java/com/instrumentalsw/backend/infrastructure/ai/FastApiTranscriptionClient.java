package com.instrumentalsw.backend.infrastructure.ai;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.instrumentalsw.backend.application.TranscriptionGateway;
import com.instrumentalsw.backend.application.TranscriptionUpload;
import com.instrumentalsw.backend.domain.InputMode;
import com.instrumentalsw.backend.domain.SaxophoneType;
import com.instrumentalsw.backend.domain.TranscriptionException;
import com.instrumentalsw.backend.domain.TranscriptionJob;
import com.instrumentalsw.backend.domain.UploadErrorCode;
import java.io.IOException;
import java.util.UUID;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

public final class FastApiTranscriptionClient implements TranscriptionGateway {
    private static final String TRANSCRIPTIONS_PATH = "/api/v1/transcriptions";
    private final RestClient restClient;
    private final ObjectMapper objectMapper;

    public FastApiTranscriptionClient(AiServiceProperties properties, ObjectMapper objectMapper) {
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
    public TranscriptionJob submit(TranscriptionUpload upload) {
        try {
            MultiValueMap<String, Object> multipart = multipart(upload);
            return restClient
                    .post()
                    .uri(TRANSCRIPTIONS_PATH)
                    .contentType(MediaType.MULTIPART_FORM_DATA)
                    .body(multipart)
                    .exchange((request, response) -> {
                        int status = response.getStatusCode().value();
                        byte[] body = readBody(response);
                        if (status != 202) {
                            throw uploadError(status);
                        }
                        return parse(body);
                    });
        } catch (TranscriptionException error) {
            throw error;
        } catch (ResourceAccessException error) {
            throw unavailable(error);
        } catch (RuntimeException error) {
            throw serviceError(error);
        }
    }

    @Override
    public TranscriptionJob get(UUID jobId) {
        try {
            return restClient.get().uri(TRANSCRIPTIONS_PATH + "/{jobId}", jobId).exchange((request, response) -> {
                int status = response.getStatusCode().value();
                byte[] body = readBody(response);
                if (status != 200) {
                    throw statusError(status);
                }
                TranscriptionJob job = parse(body);
                if (!job.jobId().equals(jobId)) {
                    throw serviceError(new IllegalArgumentException("upstream job ID mismatch"));
                }
                return job;
            });
        } catch (TranscriptionException error) {
            throw error;
        } catch (ResourceAccessException error) {
            throw unavailable(error);
        } catch (RuntimeException error) {
            throw serviceError(error);
        }
    }

    private MultiValueMap<String, Object> multipart(TranscriptionUpload upload) {
        LinkedMultiValueMap<String, Object> parts = new LinkedMultiValueMap<>();
        HttpHeaders fileHeaders = new HttpHeaders();
        if (upload.contentType() != null) {
            fileHeaders.set(HttpHeaders.CONTENT_TYPE, upload.contentType());
        }
        ByteArrayResource audio = new ByteArrayResource(upload.content()) {
            @Override
            public String getFilename() {
                return upload.filename();
            }
        };
        parts.add("file", new HttpEntity<>(audio, fileHeaders));
        parts.add("saxophone_type", upload.saxophoneType().value());
        parts.add("input_mode", upload.inputMode().value());
        return parts;
    }

    private TranscriptionJob parse(byte[] body) {
        try {
            FastApiResponse response = objectMapper.readValue(body, FastApiResponse.class);
            return new TranscriptionJob(
                    UUID.fromString(response.jobId()),
                    response.status(),
                    response.filename(),
                    response.sizeBytes(),
                    response.audioSha256(),
                    SaxophoneType.fromValue(response.saxophoneType()),
                    InputMode.fromValue(response.inputMode()));
        } catch (TranscriptionException error) {
            throw serviceError(error);
        } catch (IOException | IllegalArgumentException | NullPointerException error) {
            throw serviceError(error);
        }
    }

    private static byte[] readBody(ClientHttpResponse response) {
        try {
            return response.getBody().readAllBytes();
        } catch (IOException error) {
            throw serviceError(error);
        }
    }

    private static TranscriptionException uploadError(int status) {
        return switch (status) {
            case 400 -> new TranscriptionException(
                    UploadErrorCode.INVALID_TRANSCRIPTION_REQUEST,
                    "The transcription request was rejected.",
                    null,
                    400);
            case 413 -> new TranscriptionException(
                    UploadErrorCode.AUDIO_SIZE_LIMIT_EXCEEDED, "The audio exceeds the accepted size limit.", "file");
            case 415 -> new TranscriptionException(
                    UploadErrorCode.UNSUPPORTED_AUDIO_FORMAT, "Only MP3 and WAV files are supported.", "file");
            case 422 -> new TranscriptionException(
                    UploadErrorCode.INVALID_TRANSCRIPTION_REQUEST, "The transcription request is invalid.", null);
            default -> serviceError(new IllegalStateException("unexpected upstream upload status"));
        };
    }

    private static TranscriptionException statusError(int status) {
        return switch (status) {
            case 404 -> new TranscriptionException(
                    UploadErrorCode.TRANSCRIPTION_NOT_FOUND, "Transcription job not found.", "job_id");
            case 422 -> new TranscriptionException(
                    UploadErrorCode.INVALID_JOB_ID, "Job ID must be a valid UUID.", "job_id");
            default -> serviceError(new IllegalStateException("unexpected upstream status response"));
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

    private record FastApiResponse(
            @JsonProperty("job_id") String jobId,
            String status,
            String filename,
            @JsonProperty("size_bytes") long sizeBytes,
            @JsonProperty("audio_sha256") String audioSha256,
            @JsonProperty("saxophone_type") String saxophoneType,
            @JsonProperty("input_mode") String inputMode) {}
}
