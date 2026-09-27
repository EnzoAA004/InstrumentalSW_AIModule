package com.instrumentalsw.backend.domain;

public enum ArtifactType {
    MIDI("midi", "audio/midi", ".mid"),
    MUSICXML("musicxml", "application/vnd.recordare.musicxml+xml", ".musicxml"),
    SVG("svg", "image/svg+xml", ".svg");

    private final String value;
    private final String mediaType;
    private final String extension;

    ArtifactType(String value, String mediaType, String extension) {
        this.value = value;
        this.mediaType = mediaType;
        this.extension = extension;
    }

    public String value() {
        return value;
    }

    public String mediaType() {
        return mediaType;
    }

    public String extension() {
        return extension;
    }

    public static ArtifactType fromValue(String value) {
        for (ArtifactType type : values()) {
            if (type.value.equals(value)) {
                return type;
            }
        }
        throw new IllegalArgumentException("unsupported artifact type");
    }
}
