package com.instrumentalsw.backend.domain;

public record TranscriptionReviewEvent(
        int index,
        int pitchConcertMidi,
        int writtenPitchMidi,
        double onsetSeconds,
        double offsetSeconds,
        int velocity,
        double confidence,
        boolean isLowConfidence) {
    public TranscriptionReviewEvent {
        if (index < 0) {
            throw new IllegalArgumentException("index must be non-negative");
        }
        validateMidi("pitchConcertMidi", pitchConcertMidi);
        validateMidi("writtenPitchMidi", writtenPitchMidi);
        if (!Double.isFinite(onsetSeconds) || onsetSeconds < 0) {
            throw new IllegalArgumentException("onsetSeconds must be finite and non-negative");
        }
        if (!Double.isFinite(offsetSeconds) || offsetSeconds <= onsetSeconds) {
            throw new IllegalArgumentException("offsetSeconds must be finite and greater than onsetSeconds");
        }
        validateMidi("velocity", velocity);
        if (!Double.isFinite(confidence) || confidence < 0 || confidence > 1) {
            throw new IllegalArgumentException("confidence must be finite from zero to one");
        }
    }

    private static void validateMidi(String field, int value) {
        if (value < 0 || value > 127) {
            throw new IllegalArgumentException(field + " must be from zero to 127");
        }
    }
}
