package com.instrumentalsw.backend.web;

import com.instrumentalsw.backend.application.DownloadRevisionArtifact;
import com.instrumentalsw.backend.application.GetRevisionArtifacts;
import com.instrumentalsw.backend.domain.RevisionArtifactDownload;
import com.instrumentalsw.backend.domain.TranscriptionException;
import com.instrumentalsw.backend.domain.UploadErrorCode;
import java.util.UUID;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/transcriptions")
public final class TranscriptionArtifactController {
    private final GetRevisionArtifacts getArtifacts;
    private final DownloadRevisionArtifact downloadArtifact;

    public TranscriptionArtifactController(
            GetRevisionArtifacts getArtifacts, DownloadRevisionArtifact downloadArtifact) {
        this.getArtifacts = getArtifacts;
        this.downloadArtifact = downloadArtifact;
    }

    @GetMapping("/{jobId}/revisions/{revisionNumber}/artifacts")
    public ResponseEntity<RevisionArtifactListResponse> list(
            @PathVariable String jobId, @PathVariable String revisionNumber) {
        UUID parsedJobId = parseJobId(jobId);
        int parsedRevision = parseRevisionNumber(revisionNumber);
        return ResponseEntity.ok(RevisionArtifactListResponse.from(getArtifacts.execute(parsedJobId, parsedRevision)));
    }

    @GetMapping("/{jobId}/revisions/{revisionNumber}/artifacts/{artifactId}")
    public ResponseEntity<byte[]> download(
            @PathVariable String jobId, @PathVariable String revisionNumber, @PathVariable String artifactId) {
        UUID parsedJobId = parseJobId(jobId);
        int parsedRevision = parseRevisionNumber(revisionNumber);
        RevisionArtifactDownload download = downloadArtifact.execute(parsedJobId, parsedRevision, artifactId);
        var descriptor = download.descriptor();
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_TYPE, descriptor.mediaType())
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + descriptor.filename() + "\"")
                .header(HttpHeaders.CONTENT_LENGTH, Integer.toString(descriptor.sizeBytes()))
                .header(HttpHeaders.CACHE_CONTROL, "private, no-store")
                .header("X-Content-Type-Options", "nosniff")
                .header("X-Content-SHA256", descriptor.sha256())
                .header(HttpHeaders.ETAG, "\"sha256-" + descriptor.sha256() + "\"")
                .body(download.content());
    }

    private static UUID parseJobId(String value) {
        try {
            return UUID.fromString(value);
        } catch (IllegalArgumentException error) {
            throw new TranscriptionException(UploadErrorCode.INVALID_JOB_ID, "Job ID must be a valid UUID.", "job_id");
        }
    }

    private static int parseRevisionNumber(String value) {
        try {
            int parsed = Integer.parseInt(value);
            if (parsed < 0 || !Integer.toString(parsed).equals(value)) {
                throw new NumberFormatException();
            }
            return parsed;
        } catch (NumberFormatException error) {
            throw new TranscriptionException(
                    UploadErrorCode.REVISION_NOT_FOUND, "Transcription revision not found.", "revision_number");
        }
    }
}
