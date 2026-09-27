package com.instrumentalsw.backend.domain;

import java.util.List;
import java.util.Objects;
import java.util.UUID;

public record TranscriptionRevisionHistory(
        UUID jobId, int latestRevisionNumber, int revisionCount, List<TranscriptionRevisionHistoryEntry> revisions) {
    public TranscriptionRevisionHistory {
        Objects.requireNonNull(jobId, "jobId");
        revisions = List.copyOf(Objects.requireNonNull(revisions, "revisions"));
        if (revisionCount < 1 || revisionCount != revisions.size()) {
            throw new IllegalArgumentException("revisionCount must match a non-empty history");
        }
        for (int index = 0; index < revisions.size(); index++) {
            if (revisions.get(index).revisionNumber() != index) {
                throw new IllegalArgumentException("revision history must be sequential from zero");
            }
        }
        if (latestRevisionNumber != revisionCount - 1) {
            throw new IllegalArgumentException("latestRevisionNumber must identify the final revision");
        }
    }
}
