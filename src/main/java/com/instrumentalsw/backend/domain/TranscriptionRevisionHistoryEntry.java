package com.instrumentalsw.backend.domain;

import java.time.Instant;
import java.util.Objects;

public record TranscriptionRevisionHistoryEntry(
        int revisionNumber,
        Integer parentRevisionNumber,
        Instant createdAt,
        int eventCount,
        int modelEventCount,
        int humanEventCount,
        DerivedArtifactsStatus derivedArtifactsStatus) {
    public TranscriptionRevisionHistoryEntry {
        if (revisionNumber < 0 || eventCount < 0 || modelEventCount < 0 || humanEventCount < 0) {
            throw new IllegalArgumentException("history values must be non-negative");
        }
        Integer expectedParent = revisionNumber == 0 ? null : revisionNumber - 1;
        if (!Objects.equals(parentRevisionNumber, expectedParent)) {
            throw new IllegalArgumentException("history parent must be the prior revision");
        }
        if (eventCount != modelEventCount + humanEventCount) {
            throw new IllegalArgumentException("history counts must be consistent");
        }
        Objects.requireNonNull(createdAt, "createdAt");
        Objects.requireNonNull(derivedArtifactsStatus, "derivedArtifactsStatus");
    }
}
