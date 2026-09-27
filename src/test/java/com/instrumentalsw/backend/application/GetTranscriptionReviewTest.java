package com.instrumentalsw.backend.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.instrumentalsw.backend.domain.SaxophoneType;
import com.instrumentalsw.backend.domain.TranscriptionReview;
import com.instrumentalsw.backend.domain.TranscriptionReviewEvent;
import com.instrumentalsw.backend.domain.TranscriptionReviewSummary;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class GetTranscriptionReviewTest {
    private static final UUID JOB_ID = UUID.fromString("11111111-1111-1111-1111-111111111111");

    @Test
    void delegatesOnceWithExactUuidAndPreservesReturnedInstance() {
        TranscriptionReview expected = review();
        RecordingGateway gateway = new RecordingGateway(expected);

        TranscriptionReview actual = new GetTranscriptionReview(gateway).execute(JOB_ID);

        assertThat(actual).isSameAs(expected);
        assertThat(gateway.calls).isEqualTo(1);
        assertThat(gateway.jobId).isEqualTo(JOB_ID);
    }

    private static TranscriptionReview review() {
        return new TranscriptionReview(
                JOB_ID,
                "1.0",
                "1.0",
                "1.0",
                "1.0",
                SaxophoneType.ALTO,
                0.5,
                "model_signal_not_calibrated_accuracy",
                "model_probability",
                new TranscriptionReviewSummary(1, 1),
                List.of(new TranscriptionReviewEvent(0, 60, 69, 0.0, 0.5, 90, 0.42, true)));
    }

    private static final class RecordingGateway implements TranscriptionReviewGateway {
        private final TranscriptionReview result;
        private int calls;
        private UUID jobId;

        private RecordingGateway(TranscriptionReview result) {
            this.result = result;
        }

        @Override
        public TranscriptionReview get(UUID jobId) {
            calls++;
            this.jobId = jobId;
            return result;
        }
    }
}
