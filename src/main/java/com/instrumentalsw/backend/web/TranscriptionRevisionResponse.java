package com.instrumentalsw.backend.web;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.instrumentalsw.backend.domain.TranscriptionRevision;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record TranscriptionRevisionResponse(
        @JsonProperty("job_id") UUID jobId,
        @JsonProperty("revision_number") int revisionNumber,
        @JsonProperty("parent_revision_number") Integer parentRevisionNumber,
        @JsonProperty("created_at") Instant createdAt,
        @JsonProperty("saxophone_type") String saxophoneType,
        List<Event> events,
        Summary summary,
        @JsonProperty("derived_artifacts_status") String derivedArtifactsStatus,
        @JsonProperty("schema_version") String schemaVersion) {
    static TranscriptionRevisionResponse from(TranscriptionRevision revision) {
        return new TranscriptionRevisionResponse(
                revision.jobId(),
                revision.revisionNumber(),
                revision.parentRevisionNumber(),
                revision.createdAt(),
                revision.saxophoneType().value(),
                revision.events().stream().map(Event::from).toList(),
                new Summary(
                        revision.summary().eventCount(),
                        revision.summary().modelEventCount(),
                        revision.summary().humanEventCount()),
                revision.derivedArtifactsStatus().name(),
                revision.schemaVersion());
    }

    public record Event(
            @JsonProperty("event_id") String eventId,
            String origin,
            @JsonProperty("source_index") Integer sourceIndex,
            @JsonProperty("pitch_concert_midi") int pitchConcertMidi,
            @JsonProperty("written_pitch_midi") int writtenPitchMidi,
            @JsonProperty("onset_seconds") double onsetSeconds,
            @JsonProperty("offset_seconds") double offsetSeconds,
            int velocity,
            Double confidence,
            @JsonProperty("is_low_confidence") Boolean isLowConfidence) {
        static Event from(com.instrumentalsw.backend.domain.TranscriptionRevisionEvent event) {
            return new Event(
                    event.eventId(),
                    event.origin().value(),
                    event.sourceIndex(),
                    event.pitchConcertMidi(),
                    event.writtenPitchMidi(),
                    event.onsetSeconds(),
                    event.offsetSeconds(),
                    event.velocity(),
                    event.confidence(),
                    event.isLowConfidence());
        }
    }

    public record Summary(
            @JsonProperty("event_count") int eventCount,
            @JsonProperty("model_event_count") int modelEventCount,
            @JsonProperty("human_event_count") int humanEventCount) {}
}
