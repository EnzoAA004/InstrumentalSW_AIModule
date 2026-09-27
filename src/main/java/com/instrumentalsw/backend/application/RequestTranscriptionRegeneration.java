package com.instrumentalsw.backend.application;

import com.instrumentalsw.backend.domain.RegenerationRequest;
import java.util.UUID;

public final class RequestTranscriptionRegeneration {
    private final TranscriptionRevisionGateway gateway;

    public RequestTranscriptionRegeneration(TranscriptionRevisionGateway gateway) {
        this.gateway = gateway;
    }

    public RegenerationRequest execute(UUID jobId, int revisionNumber) {
        return gateway.requestRegeneration(jobId, revisionNumber);
    }
}
