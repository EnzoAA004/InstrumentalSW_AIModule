package com.instrumentalsw.backend.application;

import com.instrumentalsw.backend.domain.InputMode;
import com.instrumentalsw.backend.domain.SaxophoneType;
import java.util.Objects;

public record TranscriptionUpload(
        String filename, String contentType, byte[] content, SaxophoneType saxophoneType, InputMode inputMode) {
    public TranscriptionUpload {
        Objects.requireNonNull(filename, "filename");
        Objects.requireNonNull(content, "content");
        Objects.requireNonNull(saxophoneType, "saxophoneType");
        Objects.requireNonNull(inputMode, "inputMode");
        content = content.clone();
    }

    @Override
    public byte[] content() {
        return content.clone();
    }
}
