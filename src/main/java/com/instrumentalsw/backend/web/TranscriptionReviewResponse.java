package com.instrumentalsw.backend.web;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.instrumentalsw.backend.domain.TranscriptionReview;
import java.util.List;
import java.util.UUID;

public record TranscriptionReviewResponse(
        @JsonProperty("job_id") UUID jobId,
        @JsonProperty("schema_version") String schemaVersion,
        @JsonProperty("note_event_schema_version") String noteEventSchemaVersion,
        @JsonProperty("low_confidence_policy_version") String lowConfidencePolicyVersion,
        @JsonProperty("written_pitch_policy_version") String writtenPitchPolicyVersion,
        @JsonProperty("saxophone_type") String saxophoneType,
        @JsonProperty("low_confidence_threshold") double lowConfidenceThreshold,
        @JsonProperty("confidence_interpretation") String confidenceInterpretation,
        @JsonProperty("confidence_method") String confidenceMethod,
        Summary summary,
        List<Event> events) {
    static TranscriptionReviewResponse from(TranscriptionReview review) {
        return new TranscriptionReviewResponse(
                review.jobId(),
                review.schemaVersion(),
                review.noteEventSchemaVersion(),
                review.lowConfidencePolicyVersion(),
                review.writtenPitchPolicyVersion(),
                review.saxophoneType().value(),
                review.lowConfidenceThreshold(),
                review.confidenceInterpretation(),
                review.confidenceMethod(),
                new Summary(review.summary().eventCount(), review.summary().lowConfidenceCount()),
                review.events().stream().map(Event::from).toList());
    }

    public record Summary(
            @JsonProperty("event_count") int eventCount,
            @JsonProperty("low_confidence_count") int lowConfidenceCount) {}

    public record Event(
            int index,
            @JsonProperty("pitch_concert_midi") int pitchConcertMidi,
            @JsonProperty("written_pitch_midi") int writtenPitchMidi,
            @JsonProperty("onset_seconds") double onsetSeconds,
            @JsonProperty("offset_seconds") double offsetSeconds,
            int velocity,
            double confidence,
            @JsonProperty("is_low_confidence") boolean isLowConfidence) {
        static Event from(com.instrumentalsw.backend.domain.TranscriptionReviewEvent event) {
            return new Event(
                    event.index(),
                    event.pitchConcertMidi(),
                    event.writtenPitchMidi(),
                    event.onsetSeconds(),
                    event.offsetSeconds(),
                    event.velocity(),
                    event.confidence(),
                    event.isLowConfidence());
        }
    }
}
