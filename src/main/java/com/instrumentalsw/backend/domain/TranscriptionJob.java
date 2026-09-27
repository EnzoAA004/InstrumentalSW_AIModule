package com.instrumentalsw.backend.domain;

import java.util.Objects;
import java.util.UUID;
import java.util.regex.Pattern;

public record TranscriptionJob(
        UUID jobId,
        String status,
        String filename,
        long sizeBytes,
        String audioSha256,
        SaxophoneType saxophoneType,
        InputMode inputMode) {
    private static final Pattern SHA256 = Pattern.compile("[0-9a-f]{64}");

    public TranscriptionJob {
        Objects.requireNonNull(jobId, "jobId");
        Objects.requireNonNull(saxophoneType, "saxophoneType");
        Objects.requireNonNull(inputMode, "inputMode");
        if (status == null || status.isBlank()) {
            throw new IllegalArgumentException("status must not be blank");
        }
        if (filename == null || filename.isBlank() || filename.contains("/") || filename.contains("\\")) {
            throw new IllegalArgumentException("filename must be a safe basename");
        }
        if (sizeBytes < 0) {
            throw new IllegalArgumentException("sizeBytes must be non-negative");
        }
        if (audioSha256 == null || !SHA256.matcher(audioSha256).matches()) {
            throw new IllegalArgumentException("audioSha256 must be lowercase SHA-256");
        }
    }
}
