package com.instrumentalsw.backend.domain;

import java.util.regex.Pattern;

public record RevisionArtifactDescriptor(
        String artifactId,
        ArtifactType artifactType,
        String filename,
        String mediaType,
        String extension,
        int sizeBytes,
        String sha256,
        int order) {
    private static final Pattern ID = Pattern.compile("^[a-z0-9]+(?:-[a-z0-9]+)*$");
    private static final Pattern FILENAME = Pattern.compile("^[A-Za-z0-9][A-Za-z0-9._-]*$");
    private static final Pattern SHA = Pattern.compile("^[0-9a-f]{64}$");

    public RevisionArtifactDescriptor {
        if (artifactId == null || !ID.matcher(artifactId).matches()) {
            throw new IllegalArgumentException("artifactId must be a safe stable identifier");
        }
        if (artifactType == null) {
            throw new IllegalArgumentException("artifactType is required");
        }
        if (filename == null
                || filename.isBlank()
                || filename.startsWith(".")
                || filename.contains("..")
                || filename.contains("/")
                || filename.contains("\\")
                || filename.contains("\r")
                || filename.contains("\n")
                || !FILENAME.matcher(filename).matches()) {
            throw new IllegalArgumentException("filename must be a safe relative basename");
        }
        if (!artifactType.mediaType().equals(mediaType)) {
            throw new IllegalArgumentException("mediaType is incompatible with artifactType");
        }
        if (!artifactType.extension().equals(extension) || !filename.endsWith(extension)) {
            throw new IllegalArgumentException("extension is incompatible with artifactType");
        }
        if (sizeBytes <= 0) {
            throw new IllegalArgumentException("sizeBytes must be positive");
        }
        if (sha256 == null || !SHA.matcher(sha256).matches()) {
            throw new IllegalArgumentException("sha256 must be lowercase hexadecimal");
        }
        if (order < 0) {
            throw new IllegalArgumentException("order must be non-negative");
        }
    }
}
