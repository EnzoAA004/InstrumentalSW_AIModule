package com.instrumentalsw.backend.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.instrumentalsw.backend.domain.ArtifactType;
import com.instrumentalsw.backend.domain.RevisionArtifactDescriptor;
import com.instrumentalsw.backend.domain.RevisionArtifactDownload;
import com.instrumentalsw.backend.domain.RevisionArtifactList;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class TranscriptionArtifactUseCasesTest {
    private static final UUID JOB_ID = UUID.fromString("11111111-1111-1111-1111-111111111111");

    @Test
    void listDelegatesOnceAndPreservesAuthoritativeInstance() {
        RevisionArtifactList expected = list();
        RecordingGateway gateway = new RecordingGateway(expected, download());

        RevisionArtifactList actual = new GetRevisionArtifacts(gateway).execute(JOB_ID, 2);

        assertThat(actual).isSameAs(expected);
        assertThat(gateway.listCalls).isEqualTo(1);
        assertThat(gateway.jobId).isEqualTo(JOB_ID);
        assertThat(gateway.revisionNumber).isEqualTo(2);
    }

    @Test
    void downloadDelegatesExactArtifactIdentityAndPreservesBytes() {
        RevisionArtifactDownload expected = download();
        RecordingGateway gateway = new RecordingGateway(list(), expected);

        RevisionArtifactDownload actual = new DownloadRevisionArtifact(gateway).execute(JOB_ID, 2, "midi");

        assertThat(actual).isSameAs(expected);
        assertThat(actual.content()).containsExactly(1, 2, 3, 4);
        assertThat(gateway.downloadCalls).isEqualTo(1);
        assertThat(gateway.artifactId).isEqualTo("midi");
    }

    private static RevisionArtifactList list() {
        return new RevisionArtifactList(
                JOB_ID,
                2,
                List.of(new RevisionArtifactDescriptor(
                        "midi",
                        ArtifactType.MIDI,
                        "transcription-r2.mid",
                        "audio/midi",
                        ".mid",
                        4,
                        "9f64a747e1b97f131fabb6b447296c9b6f0201e79fb3c5356e6c77e89b6a806a",
                        0)));
    }

    private static RevisionArtifactDownload download() {
        return new RevisionArtifactDownload(list().artifacts().getFirst(), new byte[] {1, 2, 3, 4});
    }

    private static final class RecordingGateway implements TranscriptionArtifactGateway {
        private final RevisionArtifactList list;
        private final RevisionArtifactDownload download;
        private int listCalls;
        private int downloadCalls;
        private UUID jobId;
        private int revisionNumber;
        private String artifactId;

        private RecordingGateway(RevisionArtifactList list, RevisionArtifactDownload download) {
            this.list = list;
            this.download = download;
        }

        @Override
        public RevisionArtifactList list(UUID jobId, int revisionNumber) {
            listCalls += 1;
            this.jobId = jobId;
            this.revisionNumber = revisionNumber;
            return list;
        }

        @Override
        public RevisionArtifactDownload download(UUID jobId, int revisionNumber, String artifactId) {
            downloadCalls += 1;
            this.jobId = jobId;
            this.revisionNumber = revisionNumber;
            this.artifactId = artifactId;
            return download;
        }
    }
}
