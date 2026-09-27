package com.instrumentalsw.backend.application;

import com.instrumentalsw.backend.domain.RevisionArtifactList;
import java.util.UUID;

public final class GetRevisionArtifacts {
    private final TranscriptionArtifactGateway gateway;

    public GetRevisionArtifacts(TranscriptionArtifactGateway gateway) {
        this.gateway = gateway;
    }

    public RevisionArtifactList execute(UUID jobId, int revisionNumber) {
        return gateway.list(jobId, revisionNumber);
    }
}
