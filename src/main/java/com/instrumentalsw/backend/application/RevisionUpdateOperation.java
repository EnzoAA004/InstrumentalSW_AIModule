package com.instrumentalsw.backend.application;

public record RevisionUpdateOperation(String eventId, int writtenPitchMidi, double onsetSeconds, double offsetSeconds)
        implements RevisionOperation {
    public RevisionUpdateOperation {
        if (eventId == null || eventId.isBlank()) {
            throw new IllegalArgumentException("eventId must be non-blank");
        }
    }

    @Override
    public String type() {
        return "update";
    }
}
