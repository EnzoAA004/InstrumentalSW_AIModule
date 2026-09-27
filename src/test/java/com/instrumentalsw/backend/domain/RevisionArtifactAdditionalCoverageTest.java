package com.instrumentalsw.backend.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class RevisionArtifactAdditionalCoverageTest {
    private static final UUID JOB_ID = UUID.fromString("11111111-1111-1111-1111-111111111111");
    private static final String SHA = "9f64a747e1b97f131fabb6b447296c9b6f0201e79fb3c5356e6c77e89b6a806a";

    @Test
    void validatesEverySupportedArtifactTypeAndRejectsUnknownValue() {
        assertThat(ArtifactType.fromValue("midi")).isEqualTo(ArtifactType.MIDI);
        assertThat(ArtifactType.fromValue("musicxml")).isEqualTo(ArtifactType.MUSICXML);
        assertThat(ArtifactType.fromValue("svg")).isEqualTo(ArtifactType.SVG);
        assertThatThrownBy(() -> ArtifactType.fromValue("pdf")).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void rejectsMissingOrIncompatibleDescriptorFields() {
        assertThatThrownBy(() -> descriptor(null, "score.mid", "audio/midi", ".mid", 4, SHA, 0))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() ->
                        new RevisionArtifactDescriptor("midi", null, "score.mid", "audio/midi", ".mid", 4, SHA, 0))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> descriptor("midi", "score.mid", "audio/midi", ".svg", 4, SHA, 0))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> descriptor("midi", "score.mid", "audio/midi", ".mid", 0, SHA, 0))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> descriptor("midi", "score.mid", "audio/midi", ".mid", 4, null, 0))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> descriptor("midi", "score.mid", "audio/midi", ".mid", 4, SHA, -1))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void rejectsMissingDownloadValuesAndReturnsDefensiveCopies() {
        RevisionArtifactDescriptor descriptor = descriptor("midi", "score.mid", "audio/midi", ".mid", 4, SHA, 0);
        assertThatThrownBy(() -> new RevisionArtifactDownload(null, new byte[] {1, 2, 3, 4}))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new RevisionArtifactDownload(descriptor, null))
                .isInstanceOf(IllegalArgumentException.class);

        byte[] source = new byte[] {1, 2, 3, 4};
        RevisionArtifactDownload download = new RevisionArtifactDownload(descriptor, source);
        source[0] = 9;
        byte[] returned = download.content();
        returned[1] = 9;

        assertThat(download.content()).containsExactly(1, 2, 3, 4);
    }

    @Test
    void rejectsMissingInvalidAndEmptyListings() {
        RevisionArtifactDescriptor descriptor = descriptor("midi", "score.mid", "audio/midi", ".mid", 4, SHA, 0);
        assertThatThrownBy(() -> new RevisionArtifactList(null, 0, List.of(descriptor)))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new RevisionArtifactList(JOB_ID, -1, List.of(descriptor)))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new RevisionArtifactList(JOB_ID, 0, List.of()))
                .isInstanceOf(IllegalArgumentException.class);
    }

    private static RevisionArtifactDescriptor descriptor(
            String id, String filename, String mediaType, String extension, int size, String sha, int order) {
        return new RevisionArtifactDescriptor(id, ArtifactType.MIDI, filename, mediaType, extension, size, sha, order);
    }
}
