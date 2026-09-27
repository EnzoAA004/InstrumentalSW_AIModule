package com.instrumentalsw.backend.domain;

public final class TranscriptionException extends RuntimeException {
    private final UploadErrorCode code;
    private final String field;
    private final int publicStatus;

    public TranscriptionException(UploadErrorCode code, String message, String field) {
        this(code, message, field, defaultStatus(code), null);
    }

    public TranscriptionException(UploadErrorCode code, String message, String field, Throwable cause) {
        this(code, message, field, defaultStatus(code), cause);
    }

    public TranscriptionException(UploadErrorCode code, String message, String field, int publicStatus) {
        this(code, message, field, publicStatus, null);
    }

    private TranscriptionException(
            UploadErrorCode code, String message, String field, int publicStatus, Throwable cause) {
        super(message, cause);
        if (publicStatus < 400 || publicStatus > 599) {
            throw new IllegalArgumentException("publicStatus must be an HTTP error status");
        }
        this.code = code;
        this.field = field;
        this.publicStatus = publicStatus;
    }

    public UploadErrorCode code() {
        return code;
    }

    public String field() {
        return field;
    }

    public int publicStatus() {
        return publicStatus;
    }

    private static int defaultStatus(UploadErrorCode code) {
        return switch (code) {
            case AUDIO_FILE_REQUIRED,
                    EMPTY_AUDIO_FILE,
                    INVALID_SAXOPHONE_TYPE,
                    INVALID_INPUT_MODE,
                    INVALID_JOB_ID -> 400;
            case TRANSCRIPTION_NOT_FOUND, REVISION_NOT_FOUND, ARTIFACT_NOT_FOUND -> 404;
            case TRANSCRIPTION_RESULT_NOT_READY, REVISION_CONFLICT, ARTIFACTS_NOT_READY -> 409;
            case UNSUPPORTED_AUDIO_FORMAT -> 415;
            case AUDIO_SIZE_LIMIT_EXCEEDED -> 413;
            case INVALID_TRANSCRIPTION_REQUEST, INVALID_REVISION_OPERATION, INVALID_REVISION_EVENT -> 422;
            case AI_SERVICE_UNAVAILABLE, AI_SERVICE_ERROR -> 502;
        };
    }
}
