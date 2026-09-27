package com.instrumentalsw.backend.web;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.instrumentalsw.backend.domain.RegenerationRequest;
import java.util.List;
import java.util.UUID;

public record RegenerationRequestResponse(
        @JsonProperty("request_id") UUID requestId,
        @JsonProperty("job_id") UUID jobId,
        @JsonProperty("revision_number") int revisionNumber,
        String status,
        @JsonProperty("requested_artifacts") List<String> requestedArtifacts) {
    static RegenerationRequestResponse from(RegenerationRequest request) {
        return new RegenerationRequestResponse(
                request.requestId(),
                request.jobId(),
                request.revisionNumber(),
                request.status().name(),
                request.requestedArtifacts());
    }
}
