package com.instrumentalsw.backend.application;

import com.instrumentalsw.backend.domain.TranscriptionJob;
import java.util.UUID;

public interface TranscriptionGateway {
    TranscriptionJob submit(TranscriptionUpload upload);

    default TranscriptionJob get(UUID jobId) {
        throw new UnsupportedOperationException("status retrieval is not implemented");
    }
}
