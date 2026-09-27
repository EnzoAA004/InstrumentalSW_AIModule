package com.instrumentalsw.backend.application;

import com.instrumentalsw.backend.domain.RegenerationRequest;
import com.instrumentalsw.backend.domain.TranscriptionRevision;
import com.instrumentalsw.backend.domain.TranscriptionRevisionHistory;
import java.util.UUID;

public interface TranscriptionRevisionGateway {
    TranscriptionRevisionHistory history(UUID jobId);

    TranscriptionRevision get(UUID jobId, int revisionNumber);

    TranscriptionRevision create(UUID jobId, RevisionCreateCommand command);

    RegenerationRequest requestRegeneration(UUID jobId, int revisionNumber);
}
