package com.instrumentalsw.backend.domain;

import java.util.List;
import java.util.Objects;
import java.util.UUID;

public record RegenerationRequest(
        UUID requestId,
        UUID jobId,
        int revisionNumber,
        RegenerationRequestStatus status,
        List<String> requestedArtifacts) {
    private static final List<String> EXPECTED_ARTIFACTS = List.of("midi", "musicxml", "svg");

    public RegenerationRequest {
        Objects.requireNonNull(requestId, "requestId");
        Objects.requireNonNull(jobId, "jobId");
        if (revisionNumber < 0) {
            throw new IllegalArgumentException("revisionNumber must be non-negative");
        }
        if (status != RegenerationRequestStatus.REQUESTED) {
            throw new IllegalArgumentException("regeneration status must be REQUESTED");
        }
        requestedArtifacts = List.copyOf(Objects.requireNonNull(requestedArtifacts, "requestedArtifacts"));
        if (!requestedArtifacts.equals(EXPECTED_ARTIFACTS)) {
            throw new IllegalArgumentException("requested artifacts must be midi, musicxml, svg");
        }
    }
}
