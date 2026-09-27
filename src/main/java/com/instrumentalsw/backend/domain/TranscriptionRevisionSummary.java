package com.instrumentalsw.backend.domain;

public record TranscriptionRevisionSummary(int eventCount, int modelEventCount, int humanEventCount) {
    public TranscriptionRevisionSummary {
        if (eventCount < 0 || modelEventCount < 0 || humanEventCount < 0) {
            throw new IllegalArgumentException("revision counts must be non-negative");
        }
        if (eventCount != modelEventCount + humanEventCount) {
            throw new IllegalArgumentException("revision counts must be consistent");
        }
    }
}
