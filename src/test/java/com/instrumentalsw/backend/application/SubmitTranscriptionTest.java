package com.instrumentalsw.backend.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.instrumentalsw.backend.domain.InputMode;
import com.instrumentalsw.backend.domain.SaxophoneType;
import com.instrumentalsw.backend.domain.TranscriptionException;
import com.instrumentalsw.backend.domain.TranscriptionJob;
import com.instrumentalsw.backend.domain.UploadErrorCode;
import java.util.Arrays;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class SubmitTranscriptionTest {
    private static final UUID JOB_ID = UUID.fromString("11111111-1111-1111-1111-111111111111");

    @Test
    void submitsOnceWithNormalizedFilenameExactEnumsContentTypeAndUnchangedBytes() {
        RecordingGateway gateway = new RecordingGateway(job());
        SubmitTranscription useCase = new SubmitTranscription(gateway);
        byte[] content = "synthetic-audio".getBytes();

        TranscriptionJob result = useCase.execute("C:\\fakepath\\take.WAV", "audio/wav", content, "tenor", "mixture");

        assertThat(result).isEqualTo(job());
        assertThat(gateway.calls).isEqualTo(1);
        assertThat(gateway.upload.filename()).isEqualTo("take.WAV");
        assertThat(gateway.upload.contentType()).isEqualTo("audio/wav");
        assertThat(gateway.upload.saxophoneType()).isEqualTo(SaxophoneType.TENOR);
        assertThat(gateway.upload.inputMode()).isEqualTo(InputMode.MIXTURE);
        assertThat(gateway.upload.content()).containsExactly(content);

        byte[] returned = gateway.upload.content();
        returned[0] = 'X';
        assertThat(gateway.upload.content()).containsExactly(content);
    }

    @Test
    void acceptsEverySupportedCaseInsensitiveExtension() {
        RecordingGateway gateway = new RecordingGateway(job());
        SubmitTranscription useCase = new SubmitTranscription(gateway);

        for (String filename : Arrays.asList("take.wav", "TAKE.WAV", "take.mp3", "TAKE.MP3")) {
            useCase.execute(filename, null, new byte[] {1}, "alto", "solo");
        }

        assertThat(gateway.calls).isEqualTo(4);
    }

    @Test
    void validatesBeforeCallingGateway() {
        RecordingGateway gateway = new RecordingGateway(job());
        SubmitTranscription useCase = new SubmitTranscription(gateway);

        assertThatThrownBy(() -> useCase.execute("", null, new byte[] {1}, "alto", "solo"))
                .isInstanceOf(TranscriptionException.class)
                .extracting(error -> ((TranscriptionException) error).code())
                .isEqualTo(UploadErrorCode.AUDIO_FILE_REQUIRED);
        assertThatThrownBy(() -> useCase.execute("take.wav", null, new byte[0], "alto", "solo"))
                .isInstanceOf(TranscriptionException.class)
                .extracting(error -> ((TranscriptionException) error).code())
                .isEqualTo(UploadErrorCode.EMPTY_AUDIO_FILE);
        assertThatThrownBy(() -> useCase.execute("take.pdf", null, new byte[] {1}, "alto", "solo"))
                .isInstanceOf(TranscriptionException.class)
                .extracting(error -> ((TranscriptionException) error).code())
                .isEqualTo(UploadErrorCode.UNSUPPORTED_AUDIO_FORMAT);
        assertThatThrownBy(() -> useCase.execute("take.wav", null, new byte[] {1}, "clarinet", "solo"))
                .isInstanceOf(TranscriptionException.class)
                .extracting(error -> ((TranscriptionException) error).code())
                .isEqualTo(UploadErrorCode.INVALID_SAXOPHONE_TYPE);
        assertThatThrownBy(() -> useCase.execute("take.wav", null, new byte[] {1}, "alto", "stream"))
                .isInstanceOf(TranscriptionException.class)
                .extracting(error -> ((TranscriptionException) error).code())
                .isEqualTo(UploadErrorCode.INVALID_INPUT_MODE);

        assertThat(gateway.calls).isZero();
    }

    @Test
    void propagatesControlledGatewayErrorWithoutRetry() {
        TranscriptionException expected = new TranscriptionException(
                UploadErrorCode.AI_SERVICE_UNAVAILABLE, "The transcription service is unavailable.", null);
        RecordingGateway gateway = new RecordingGateway(expected);
        SubmitTranscription useCase = new SubmitTranscription(gateway);

        assertThatThrownBy(() -> useCase.execute("take.wav", "audio/wav", new byte[] {1, 2, 3}, "alto", "solo"))
                .isSameAs(expected);
        assertThat(gateway.calls).isEqualTo(1);
    }

    private static TranscriptionJob job() {
        return new TranscriptionJob(
                JOB_ID, "UPLOADED", "take.WAV", 15, "a".repeat(64), SaxophoneType.TENOR, InputMode.MIXTURE);
    }

    private static final class RecordingGateway implements TranscriptionGateway {
        private final TranscriptionJob result;
        private final TranscriptionException error;
        private int calls;
        private TranscriptionUpload upload;

        private RecordingGateway(TranscriptionJob result) {
            this.result = result;
            this.error = null;
        }

        private RecordingGateway(TranscriptionException error) {
            this.result = null;
            this.error = error;
        }

        @Override
        public TranscriptionJob submit(TranscriptionUpload upload) {
            calls++;
            this.upload = upload;
            if (error != null) {
                throw error;
            }
            return result;
        }
    }
}
