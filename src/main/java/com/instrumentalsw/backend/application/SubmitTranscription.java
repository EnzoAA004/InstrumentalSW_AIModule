package com.instrumentalsw.backend.application;

import com.instrumentalsw.backend.domain.InputMode;
import com.instrumentalsw.backend.domain.SaxophoneType;
import com.instrumentalsw.backend.domain.TranscriptionException;
import com.instrumentalsw.backend.domain.TranscriptionJob;
import com.instrumentalsw.backend.domain.UploadErrorCode;
import java.util.Locale;
import java.util.Objects;
import java.util.Set;

public final class SubmitTranscription {
    private static final Set<String> SUPPORTED_EXTENSIONS = Set.of(".mp3", ".wav");
    private final TranscriptionGateway gateway;

    public SubmitTranscription(TranscriptionGateway gateway) {
        this.gateway = Objects.requireNonNull(gateway, "gateway");
    }

    public TranscriptionJob execute(
            String filename, String contentType, byte[] content, String saxophoneType, String inputMode) {
        String safeFilename = normalizeFilename(filename);
        validateContent(content);
        validateExtension(safeFilename);
        SaxophoneType saxophone = SaxophoneType.fromValue(saxophoneType);
        InputMode mode = InputMode.fromValue(inputMode);
        String normalizedContentType = contentType == null || contentType.isBlank() ? null : contentType.trim();
        return gateway.submit(new TranscriptionUpload(safeFilename, normalizedContentType, content, saxophone, mode));
    }

    private static String normalizeFilename(String filename) {
        if (filename == null || filename.isBlank()) {
            throw new TranscriptionException(
                    UploadErrorCode.AUDIO_FILE_REQUIRED, "An MP3 or WAV audio file is required.", "file");
        }
        String normalizedPath = filename.replace('\\', '/');
        String basename =
                normalizedPath.substring(normalizedPath.lastIndexOf('/') + 1).trim();
        if (basename.isBlank()) {
            throw new TranscriptionException(
                    UploadErrorCode.AUDIO_FILE_REQUIRED, "An MP3 or WAV audio file is required.", "file");
        }
        return basename;
    }

    private static void validateContent(byte[] content) {
        if (content == null || content.length == 0) {
            throw new TranscriptionException(
                    UploadErrorCode.EMPTY_AUDIO_FILE, "The selected audio file is empty.", "file");
        }
    }

    private static void validateExtension(String filename) {
        String lower = filename.toLowerCase(Locale.ROOT);
        boolean supported = SUPPORTED_EXTENSIONS.stream().anyMatch(lower::endsWith);
        if (!supported) {
            throw new TranscriptionException(
                    UploadErrorCode.UNSUPPORTED_AUDIO_FORMAT, "Only MP3 and WAV files are supported.", "file");
        }
    }
}
