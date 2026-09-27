package com.instrumentalsw.backend.application;

import com.instrumentalsw.backend.domain.RevisionArtifactDownload;
import com.instrumentalsw.backend.domain.RevisionArtifactList;
import java.util.UUID;

public interface TranscriptionArtifactGateway {
    RevisionArtifactList list(UUID jobId, int revisionNumber);

    RevisionArtifactDownload download(UUID jobId, int revisionNumber, String artifactId);
}
