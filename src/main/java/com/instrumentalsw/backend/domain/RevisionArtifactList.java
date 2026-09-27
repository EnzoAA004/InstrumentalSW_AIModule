package com.instrumentalsw.backend.domain;

import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

public record RevisionArtifactList(UUID jobId, int revisionNumber, List<RevisionArtifactDescriptor> artifacts) {
    public RevisionArtifactList {
        if (jobId == null) {
            throw new IllegalArgumentException("jobId is required");
        }
        if (revisionNumber < 0) {
            throw new IllegalArgumentException("revisionNumber must be non-negative");
        }
        if (artifacts == null || artifacts.isEmpty()) {
            throw new IllegalArgumentException("artifacts must not be empty");
        }
        artifacts = List.copyOf(artifacts);
        Set<String> ids = new HashSet<>();
        Set<String> filenames = new HashSet<>();
        for (int index = 0; index < artifacts.size(); index++) {
            RevisionArtifactDescriptor descriptor = artifacts.get(index);
            if (descriptor == null
                    || descriptor.order() != index
                    || !ids.add(descriptor.artifactId())
                    || !filenames.add(descriptor.filename())) {
                throw new IllegalArgumentException("artifact descriptors must be unique and ordered from zero");
            }
        }
    }
}
