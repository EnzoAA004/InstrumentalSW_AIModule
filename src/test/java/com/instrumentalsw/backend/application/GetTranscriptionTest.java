package com.instrumentalsw.backend.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.instrumentalsw.backend.domain.InputMode;
import com.instrumentalsw.backend.domain.SaxophoneType;
import com.instrumentalsw.backend.domain.TranscriptionException;
import com.instrumentalsw.backend.domain.TranscriptionJob;
import com.instrumentalsw.backend.domain.UploadErrorCode;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class GetTranscriptionTest {
    private static final UUID JOB_ID = UUID.fromString("11111111-1111-1111-1111-111111111111");

    @Test
    void delegatesOnceWithTheExactUuidAndReturnsTheGatewayInstance() {
        TranscriptionJob expected = job();
        RecordingGateway gateway = new RecordingGateway(expected);
        GetTranscription useCase = new GetTranscription(gateway);

        TranscriptionJob actual = useCase.execute(JOB_ID);

        assertThat(actual).isSameAs(expected);
        assertThat(gateway.getCalls).isEqualTo(1);
        assertThat(gateway.requestedJobId).isEqualTo(JOB_ID);
        assertThat(gateway.submitCalls).isZero();
    }

    @Test
    void propagatesControlledErrorsWithoutRetryOrLocalReconstruction() {
        TranscriptionException expected = new TranscriptionException(
                UploadErrorCode.TRANSCRIPTION_NOT_FOUND, "Transcription job not found.", "job_id");
        RecordingGateway gateway = new RecordingGateway(expected);
        GetTranscription useCase = new GetTranscription(gateway);

        assertThatThrownBy(() -> useCase.execute(JOB_ID)).isSameAs(expected);
        assertThat(gateway.getCalls).isEqualTo(1);
        assertThat(gateway.requestedJobId).isEqualTo(JOB_ID);
        assertThat(gateway.submitCalls).isZero();
    }

    private static TranscriptionJob job() {
        return new TranscriptionJob(
                JOB_ID, "UPLOADED", "take.wav", 15, "a".repeat(64), SaxophoneType.ALTO, InputMode.SOLO);
    }

    private static final class RecordingGateway implements TranscriptionGateway {
        private final TranscriptionJob result;
        private final TranscriptionException error;
        private int getCalls;
        private int submitCalls;
        private UUID requestedJobId;

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
            submitCalls++;
            throw new AssertionError("status retrieval must not submit audio");
        }

        @Override
        public TranscriptionJob get(UUID jobId) {
            getCalls++;
            requestedJobId = jobId;
            if (error != null) {
                throw error;
            }
            return result;
        }
    }
}
