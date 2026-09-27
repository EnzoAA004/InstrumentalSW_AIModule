package com.instrumentalsw.backend.domain;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class RevisionArtifactContractTest {
    private static final UUID JOB_ID = UUID.fromString("11111111-1111-1111-1111-111111111111");
    private static final String SHA = "9f64a747e1b97f131fabb6b447296c9b6f0201e79fb3c5356e6c77e89b6a806a";

    @Test
    void rejectsUnsafeFilenameIncompatibleMetadataAndDuplicateOrder() {
        assertThatThrownBy(() -> new RevisionArtifactDescriptor(
                        "midi", ArtifactType.MIDI, "../score.mid", "audio/midi", ".mid", 4, SHA, 0))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new RevisionArtifactDescriptor(
                        "midi", ArtifactType.MIDI, "score.mid", "image/svg+xml", ".mid", 4, SHA, 0))
                .isInstanceOf(IllegalArgumentException.class);
        var first = descriptor("midi", "score.mid", 0);
        var second = descriptor("musicxml", "score.musicxml", 0);
        assertThatThrownBy(() -> new RevisionArtifactList(JOB_ID, 0, List.of(first, second)))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void rejectsBinaryThatDoesNotMatchDescriptorSizeOrSha() {
        var descriptor = descriptor("midi", "score.mid", 0);
        assertThatThrownBy(() -> new RevisionArtifactDownload(descriptor, new byte[] {9, 9, 9, 9}))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new RevisionArtifactDownload(descriptor, new byte[] {1, 2, 3}))
                .isInstanceOf(IllegalArgumentException.class);
    }

    private static RevisionArtifactDescriptor descriptor(String id, String filename, int order) {
        ArtifactType type = id.equals("midi") ? ArtifactType.MIDI : ArtifactType.MUSICXML;
        return new RevisionArtifactDescriptor(
                id,
                type,
                filename,
                type == ArtifactType.MIDI ? "audio/midi" : "application/vnd.recordare.musicxml+xml",
                type == ArtifactType.MIDI ? ".mid" : ".musicxml",
                4,
                SHA,
                order);
    }
}
