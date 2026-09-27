package com.instrumentalsw.backend.domain;

import java.util.Arrays;

public enum InputMode {
    SOLO("solo"),
    MIXTURE("mixture");

    private final String value;

    InputMode(String value) {
        this.value = value;
    }

    public String value() {
        return value;
    }

    public static InputMode fromValue(String value) {
        return Arrays.stream(values())
                .filter(candidate -> candidate.value.equals(value))
                .findFirst()
                .orElseThrow(() -> new TranscriptionException(
                        UploadErrorCode.INVALID_INPUT_MODE, "Select solo or mixture.", "input_mode"));
    }
}
