package com.instrumentalsw.backend.application;

import com.instrumentalsw.backend.domain.TranscriptionReview;
import java.util.UUID;

public final class GetTranscriptionReview {
    private final TranscriptionReviewGateway gateway;

    public GetTranscriptionReview(TranscriptionReviewGateway gateway) {
        this.gateway = gateway;
    }

    public TranscriptionReview execute(UUID jobId) {
        return gateway.get(jobId);
    }
}
