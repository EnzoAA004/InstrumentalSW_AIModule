package com.instrumentalsw.backend.application;

import com.instrumentalsw.backend.domain.RevisionArtifactDownload;
import java.util.UUID;

public final class DownloadRevisionArtifact {
    private final TranscriptionArtifactGateway gateway;

    public DownloadRevisionArtifact(TranscriptionArtifactGateway gateway) {
        this.gateway = gateway;
    }

    public RevisionArtifactDownload execute(UUID jobId, int revisionNumber, String artifactId) {
        return gateway.download(jobId, revisionNumber, artifactId);
    }
}
