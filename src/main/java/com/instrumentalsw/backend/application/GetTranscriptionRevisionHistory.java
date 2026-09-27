package com.instrumentalsw.backend.application;

import com.instrumentalsw.backend.domain.TranscriptionRevisionHistory;
import java.util.UUID;

public final class GetTranscriptionRevisionHistory {
    private final TranscriptionRevisionGateway gateway;

    public GetTranscriptionRevisionHistory(TranscriptionRevisionGateway gateway) {
        this.gateway = gateway;
    }

    public TranscriptionRevisionHistory execute(UUID jobId) {
        return gateway.history(jobId);
    }
}
