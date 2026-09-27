package com.instrumentalsw.backend.web;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.instrumentalsw.backend.domain.TranscriptionRevisionHistory;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record TranscriptionRevisionHistoryResponse(
        @JsonProperty("job_id") UUID jobId,
        @JsonProperty("latest_revision_number") int latestRevisionNumber,
        @JsonProperty("revision_count") int revisionCount,
        List<Entry> revisions) {
    static TranscriptionRevisionHistoryResponse from(TranscriptionRevisionHistory history) {
        return new TranscriptionRevisionHistoryResponse(
                history.jobId(),
                history.latestRevisionNumber(),
                history.revisionCount(),
                history.revisions().stream().map(Entry::from).toList());
    }

    public record Entry(
            @JsonProperty("revision_number") int revisionNumber,
            @JsonProperty("parent_revision_number") Integer parentRevisionNumber,
            @JsonProperty("created_at") Instant createdAt,
            @JsonProperty("event_count") int eventCount,
            @JsonProperty("model_event_count") int modelEventCount,
            @JsonProperty("human_event_count") int humanEventCount,
            @JsonProperty("derived_artifacts_status") String derivedArtifactsStatus) {
        static Entry from(com.instrumentalsw.backend.domain.TranscriptionRevisionHistoryEntry entry) {
            return new Entry(
                    entry.revisionNumber(),
                    entry.parentRevisionNumber(),
                    entry.createdAt(),
                    entry.eventCount(),
                    entry.modelEventCount(),
                    entry.humanEventCount(),
                    entry.derivedArtifactsStatus().name());
        }
    }
}
