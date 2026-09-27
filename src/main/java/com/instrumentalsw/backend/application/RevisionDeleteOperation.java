package com.instrumentalsw.backend.application;

public record RevisionDeleteOperation(String eventId) implements RevisionOperation {
    public RevisionDeleteOperation {
        if (eventId == null || eventId.isBlank()) {
            throw new IllegalArgumentException("eventId must be non-blank");
        }
    }

    @Override
    public String type() {
        return "delete";
    }
}
