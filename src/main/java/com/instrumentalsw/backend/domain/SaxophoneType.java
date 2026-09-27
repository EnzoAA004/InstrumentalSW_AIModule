package com.instrumentalsw.backend.domain;

import java.util.Arrays;

public enum SaxophoneType {
    SOPRANO("soprano"),
    ALTO("alto"),
    TENOR("tenor"),
    BARITONE("baritone");

    private final String value;

    SaxophoneType(String value) {
        this.value = value;
    }

    public String value() {
        return value;
    }

    public static SaxophoneType fromValue(String value) {
        return Arrays.stream(values())
                .filter(candidate -> candidate.value.equals(value))
                .findFirst()
                .orElseThrow(() -> new TranscriptionException(
                        UploadErrorCode.INVALID_SAXOPHONE_TYPE,
                        "Select soprano, alto, tenor, or baritone.",
                        "saxophone_type"));
    }
}
