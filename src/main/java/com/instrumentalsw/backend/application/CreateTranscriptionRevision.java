package com.instrumentalsw.backend.application;

import com.instrumentalsw.backend.domain.TranscriptionRevision;
import java.util.UUID;

public final class CreateTranscriptionRevision {
    private final TranscriptionRevisionGateway gateway;

    public CreateTranscriptionRevision(TranscriptionRevisionGateway gateway) {
        this.gateway = gateway;
    }

    public TranscriptionRevision execute(UUID jobId, RevisionCreateCommand command) {
        return gateway.create(jobId, command);
    }
}
