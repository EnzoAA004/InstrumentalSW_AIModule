package com.instrumentalsw.backend.application;

import com.instrumentalsw.backend.domain.TranscriptionJob;
import java.util.Objects;
import java.util.UUID;

public final class GetTranscription {
    private final TranscriptionGateway gateway;

    public GetTranscription(TranscriptionGateway gateway) {
        this.gateway = Objects.requireNonNull(gateway, "gateway");
    }

    public TranscriptionJob execute(UUID jobId) {
        return gateway.get(Objects.requireNonNull(jobId, "jobId"));
    }
}
