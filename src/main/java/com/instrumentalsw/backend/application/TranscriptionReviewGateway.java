package com.instrumentalsw.backend.application;

import com.instrumentalsw.backend.domain.TranscriptionReview;
import java.util.UUID;

public interface TranscriptionReviewGateway {
    TranscriptionReview get(UUID jobId);
}
