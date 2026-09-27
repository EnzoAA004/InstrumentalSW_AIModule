package com.instrumentalsw.backend.application;

import com.instrumentalsw.backend.domain.TranscriptionRevision;
import java.util.UUID;

public final class GetTranscriptionRevision {
    private final TranscriptionRevisionGateway gateway;

    public GetTranscriptionRevision(TranscriptionRevisionGateway gateway) {
        this.gateway = gateway;
    }

    public TranscriptionRevision execute(UUID jobId, int revisionNumber) {
        return gateway.get(jobId, revisionNumber);
    }
}
