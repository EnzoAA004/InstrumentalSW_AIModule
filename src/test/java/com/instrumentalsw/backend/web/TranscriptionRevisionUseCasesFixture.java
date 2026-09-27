package com.instrumentalsw.backend.web;

import com.instrumentalsw.backend.domain.DerivedArtifactsStatus;
import com.instrumentalsw.backend.domain.EventOrigin;
import com.instrumentalsw.backend.domain.RegenerationRequest;
import com.instrumentalsw.backend.domain.RegenerationRequestStatus;
import com.instrumentalsw.backend.domain.SaxophoneType;
import com.instrumentalsw.backend.domain.TranscriptionRevision;
import com.instrumentalsw.backend.domain.TranscriptionRevisionEvent;
import com.instrumentalsw.backend.domain.TranscriptionRevisionHistory;
import com.instrumentalsw.backend.domain.TranscriptionRevisionHistoryEntry;
import com.instrumentalsw.backend.domain.TranscriptionRevisionSummary;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

final class TranscriptionRevisionUseCasesFixture {
    private static final UUID JOB_ID = UUID.fromString("11111111-1111-1111-1111-111111111111");

    private TranscriptionRevisionUseCasesFixture() {}

    static TranscriptionRevision revision() {
        return new TranscriptionRevision(
                JOB_ID,
                1,
                0,
                Instant.parse("2026-07-22T12:00:00Z"),
                SaxophoneType.ALTO,
                List.of(
                        new TranscriptionRevisionEvent(
                                "source-0", EventOrigin.MODEL, 0, 61, 70, 0.1, 0.6, 90, 0.42, true),
                        new TranscriptionRevisionEvent(
                                "human-22222222-2222-2222-2222-222222222222",
                                EventOrigin.HUMAN,
                                null,
                                63,
                                72,
                                0.7,
                                1.0,
                                64,
                                null,
                                null)),
                new TranscriptionRevisionSummary(2, 1, 1),
                DerivedArtifactsStatus.STALE,
                "1.0");
    }

    static TranscriptionRevisionHistory history() {
        return new TranscriptionRevisionHistory(
                JOB_ID,
                1,
                2,
                List.of(
                        new TranscriptionRevisionHistoryEntry(
                                0,
                                null,
                                Instant.parse("2026-07-22T11:00:00Z"),
                                2,
                                2,
                                0,
                                DerivedArtifactsStatus.CURRENT),
                        new TranscriptionRevisionHistoryEntry(
                                1, 0, Instant.parse("2026-07-22T12:00:00Z"), 2, 1, 1, DerivedArtifactsStatus.STALE)));
    }

    static RegenerationRequest request() {
        return new RegenerationRequest(
                UUID.fromString("33333333-3333-3333-3333-333333333333"),
                JOB_ID,
                1,
                RegenerationRequestStatus.REQUESTED,
                List.of("midi", "musicxml", "svg"));
    }
}
