package com.instrumentalsw.backend.domain;

import java.time.Instant;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.UUID;

public record TranscriptionRevision(
        UUID jobId,
        int revisionNumber,
        Integer parentRevisionNumber,
        Instant createdAt,
        SaxophoneType saxophoneType,
        List<TranscriptionRevisionEvent> events,
        TranscriptionRevisionSummary summary,
        DerivedArtifactsStatus derivedArtifactsStatus,
        String schemaVersion) {
    public TranscriptionRevision {
        Objects.requireNonNull(jobId, "jobId");
        if (revisionNumber < 0) {
            throw new IllegalArgumentException("revisionNumber must be non-negative");
        }
        Integer expectedParent = revisionNumber == 0 ? null : revisionNumber - 1;
        if (!Objects.equals(parentRevisionNumber, expectedParent)) {
            throw new IllegalArgumentException("parent revision must be the prior revision");
        }
        Objects.requireNonNull(createdAt, "createdAt");
        Objects.requireNonNull(saxophoneType, "saxophoneType");
        events = List.copyOf(Objects.requireNonNull(events, "events"));
        Objects.requireNonNull(summary, "summary");
        Objects.requireNonNull(derivedArtifactsStatus, "derivedArtifactsStatus");
        if (!"1.0".equals(schemaVersion)) {
            throw new IllegalArgumentException("schemaVersion must be 1.0");
        }
        var ids = new HashSet<String>();
        int modelCount = 0;
        for (TranscriptionRevisionEvent event : events) {
            Objects.requireNonNull(event, "event");
            if (!ids.add(event.eventId())) {
                throw new IllegalArgumentException("event IDs must be unique");
            }
            if (event.origin() == EventOrigin.MODEL) {
                modelCount++;
            }
        }
        if (summary.eventCount() != events.size()
                || summary.modelEventCount() != modelCount
                || summary.humanEventCount() != events.size() - modelCount) {
            throw new IllegalArgumentException("revision summary must match events");
        }
    }
}
