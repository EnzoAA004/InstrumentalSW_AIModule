package com.instrumentalsw.backend.web;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.instrumentalsw.backend.domain.RevisionArtifactDescriptor;
import com.instrumentalsw.backend.domain.RevisionArtifactList;
import java.util.List;
import java.util.UUID;

public record RevisionArtifactListResponse(
        @JsonProperty("job_id") UUID jobId,
        @JsonProperty("revision_number") int revisionNumber,
        List<DescriptorResponse> artifacts) {
    public static RevisionArtifactListResponse from(RevisionArtifactList value) {
        return new RevisionArtifactListResponse(
                value.jobId(),
                value.revisionNumber(),
                value.artifacts().stream().map(DescriptorResponse::from).toList());
    }

    public record DescriptorResponse(
            @JsonProperty("artifact_id") String artifactId,
            @JsonProperty("artifact_type") String artifactType,
            String filename,
            @JsonProperty("media_type") String mediaType,
            String extension,
            @JsonProperty("size_bytes") int sizeBytes,
            String sha256,
            int order) {
        private static DescriptorResponse from(RevisionArtifactDescriptor value) {
            return new DescriptorResponse(
                    value.artifactId(),
                    value.artifactType().value(),
                    value.filename(),
                    value.mediaType(),
                    value.extension(),
                    value.sizeBytes(),
                    value.sha256(),
                    value.order());
        }
    }
}
