package com.instrumentalsw.backend.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.instrumentalsw.backend.application.TranscriptionUpload;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class DomainContractsTest {
    private static final UUID JOB_ID = UUID.fromString("11111111-1111-1111-1111-111111111111");

    @Test
    void parsesEverySupportedEnumValue() {
        assertThat(SaxophoneType.fromValue("soprano")).isEqualTo(SaxophoneType.SOPRANO);
        assertThat(SaxophoneType.fromValue("alto")).isEqualTo(SaxophoneType.ALTO);
        assertThat(SaxophoneType.fromValue("tenor")).isEqualTo(SaxophoneType.TENOR);
        assertThat(SaxophoneType.fromValue("baritone")).isEqualTo(SaxophoneType.BARITONE);
        assertThat(InputMode.fromValue("solo")).isEqualTo(InputMode.SOLO);
        assertThat(InputMode.fromValue("mixture")).isEqualTo(InputMode.MIXTURE);
    }

    @Test
    void validatesEveryTranscriptionJobInvariant() {
        assertThatThrownBy(() -> job(null, "UPLOADED", "take.wav", 1, "a".repeat(64)))
                .isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> job(JOB_ID, " ", "take.wav", 1, "a".repeat(64)))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> job(JOB_ID, "UPLOADED", "", 1, "a".repeat(64)))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> job(JOB_ID, "UPLOADED", "private/take.wav", 1, "a".repeat(64)))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> job(JOB_ID, "UPLOADED", "private\\take.wav", 1, "a".repeat(64)))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> job(JOB_ID, "UPLOADED", "take.wav", -1, "a".repeat(64)))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> job(JOB_ID, "UPLOADED", "take.wav", 1, "ABC"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void uploadRejectsNullFieldsAndDefensivelyCopiesBytes() {
        byte[] content = {1, 2, 3};
        TranscriptionUpload upload =
                new TranscriptionUpload("take.wav", null, content, SaxophoneType.ALTO, InputMode.SOLO);
        content[0] = 9;
        assertThat(upload.content()).containsExactly(1, 2, 3);

        assertThatThrownBy(
                        () -> new TranscriptionUpload(null, null, new byte[] {1}, SaxophoneType.ALTO, InputMode.SOLO))
                .isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> new TranscriptionUpload("take.wav", null, null, SaxophoneType.ALTO, InputMode.SOLO))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void controlledExceptionPreservesCodeFieldAndCause() {
        IllegalStateException cause = new IllegalStateException("private");
        TranscriptionException error =
                new TranscriptionException(UploadErrorCode.AI_SERVICE_ERROR, "Stable public message.", "file", cause);

        assertThat(error.code()).isEqualTo(UploadErrorCode.AI_SERVICE_ERROR);
        assertThat(error.field()).isEqualTo("file");
        assertThat(error.getMessage()).isEqualTo("Stable public message.");
        assertThat(error.getCause()).isSameAs(cause);
    }

    private static TranscriptionJob job(UUID jobId, String status, String filename, long sizeBytes, String sha256) {
        return new TranscriptionJob(jobId, status, filename, sizeBytes, sha256, SaxophoneType.ALTO, InputMode.SOLO);
    }
}
