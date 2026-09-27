package com.instrumentalsw.backend.domain;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

public record RevisionArtifactDownload(RevisionArtifactDescriptor descriptor, byte[] content) {
    public RevisionArtifactDownload {
        if (descriptor == null || content == null) {
            throw new IllegalArgumentException("descriptor and content are required");
        }
        content = content.clone();
        if (content.length != descriptor.sizeBytes()) {
            throw new IllegalArgumentException("content length must match descriptor size");
        }
        if (!digest(content).equals(descriptor.sha256())) {
            throw new IllegalArgumentException("content SHA-256 must match descriptor");
        }
    }

    @Override
    public byte[] content() {
        return content.clone();
    }

    private static String digest(byte[] content) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(content));
        } catch (NoSuchAlgorithmException error) {
            throw new IllegalStateException("SHA-256 is unavailable", error);
        }
    }
}
