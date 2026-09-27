package com.instrumentalsw.backend.domain;

import java.util.Objects;
import java.util.UUID;

public record TranscriptionRevisionEvent(
        String eventId,
        EventOrigin origin,
        Integer sourceIndex,
        int pitchConcertMidi,
        int writtenPitchMidi,
        double onsetSeconds,
        double offsetSeconds,
        int velocity,
        Double confidence,
        Boolean isLowConfidence) {
    public TranscriptionRevisionEvent {
        if (eventId == null || eventId.isBlank()) {
            throw new IllegalArgumentException("eventId must be non-blank");
        }
        Objects.requireNonNull(origin, "origin");
        requireMidi("pitchConcertMidi", pitchConcertMidi);
        requireMidi("writtenPitchMidi", writtenPitchMidi);
        requireMidi("velocity", velocity);
        if (!Double.isFinite(onsetSeconds) || onsetSeconds < 0) {
            throw new IllegalArgumentException("onsetSeconds must be finite and non-negative");
        }
        if (!Double.isFinite(offsetSeconds) || offsetSeconds <= onsetSeconds) {
            throw new IllegalArgumentException("offsetSeconds must be finite and greater than onsetSeconds");
        }
        if (origin == EventOrigin.MODEL) {
            if (sourceIndex == null || sourceIndex < 0 || !eventId.equals("source-" + sourceIndex)) {
                throw new IllegalArgumentException("model event identity must match sourceIndex");
            }
            if (confidence == null || !Double.isFinite(confidence) || confidence < 0 || confidence > 1) {
                throw new IllegalArgumentException("model event confidence must be finite from zero to one");
            }
            Objects.requireNonNull(isLowConfidence, "model event low confidence marker");
        } else {
            if (sourceIndex != null || confidence != null || isLowConfidence != null) {
                throw new IllegalArgumentException("human events must not claim model provenance or confidence");
            }
            if (!eventId.startsWith("human-")) {
                throw new IllegalArgumentException("human event ID must start with human-");
            }
            UUID.fromString(eventId.substring("human-".length()));
        }
    }

    private static void requireMidi(String field, int value) {
        if (value < 0 || value > 127) {
            throw new IllegalArgumentException(field + " must be between 0 and 127");
        }
    }
}
