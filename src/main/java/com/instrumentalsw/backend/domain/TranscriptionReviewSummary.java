package com.instrumentalsw.backend.domain;

public record TranscriptionReviewSummary(int eventCount, int lowConfidenceCount) {
    public TranscriptionReviewSummary {
        if (eventCount < 0 || lowConfidenceCount < 0 || lowConfidenceCount > eventCount) {
            throw new IllegalArgumentException("review counts must be non-negative and consistent");
        }
    }
}
