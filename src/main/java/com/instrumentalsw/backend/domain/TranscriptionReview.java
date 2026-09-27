package com.instrumentalsw.backend.domain;

import java.util.List;
import java.util.Objects;
import java.util.UUID;

public record TranscriptionReview(
        UUID jobId,
        String schemaVersion,
        String noteEventSchemaVersion,
        String lowConfidencePolicyVersion,
        String writtenPitchPolicyVersion,
        SaxophoneType saxophoneType,
        double lowConfidenceThreshold,
        String confidenceInterpretation,
        String confidenceMethod,
        TranscriptionReviewSummary summary,
        List<TranscriptionReviewEvent> events) {
    private static final String VERSION = "1.0";
    private static final String INTERPRETATION = "model_signal_not_calibrated_accuracy";

    public TranscriptionReview {
        Objects.requireNonNull(jobId, "jobId");
        requireVersion("schemaVersion", schemaVersion);
        requireVersion("noteEventSchemaVersion", noteEventSchemaVersion);
        requireVersion("lowConfidencePolicyVersion", lowConfidencePolicyVersion);
        requireVersion("writtenPitchPolicyVersion", writtenPitchPolicyVersion);
        Objects.requireNonNull(saxophoneType, "saxophoneType");
        if (!Double.isFinite(lowConfidenceThreshold) || lowConfidenceThreshold < 0 || lowConfidenceThreshold > 1) {
            throw new IllegalArgumentException("lowConfidenceThreshold must be finite from zero to one");
        }
        if (!INTERPRETATION.equals(confidenceInterpretation)) {
            throw new IllegalArgumentException("unsupported confidence interpretation");
        }
        if (confidenceMethod == null || confidenceMethod.isBlank()) {
            throw new IllegalArgumentException("confidenceMethod must be non-blank");
        }
        Objects.requireNonNull(summary, "summary");
        events = List.copyOf(Objects.requireNonNull(events, "events"));
        if (summary.eventCount() != events.size()) {
            throw new IllegalArgumentException("event count must match events");
        }
        int lowCount = 0;
        for (int index = 0; index < events.size(); index++) {
            TranscriptionReviewEvent event = Objects.requireNonNull(events.get(index), "event");
            if (event.index() != index) {
                throw new IllegalArgumentException("event indices must be consecutive from zero");
            }
            if (event.isLowConfidence()) {
                lowCount++;
            }
        }
        if (summary.lowConfidenceCount() != lowCount) {
            throw new IllegalArgumentException("low confidence count must match event markers");
        }
    }

    private static void requireVersion(String field, String value) {
        if (!VERSION.equals(value)) {
            throw new IllegalArgumentException(field + " must be " + VERSION);
        }
    }
}
