package com.instrumentalsw.backend.domain;

public enum EventOrigin {
    MODEL("model"),
    HUMAN("human");

    private final String value;

    EventOrigin(String value) {
        this.value = value;
    }

    public String value() {
        return value;
    }

    public static EventOrigin fromValue(String value) {
        for (EventOrigin origin : values()) {
            if (origin.value.equals(value)) {
                return origin;
            }
        }
        throw new IllegalArgumentException("unsupported event origin");
    }
}
