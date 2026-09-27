import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

function source(relative: string): string {
  return readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8");
}

describe("SAX-045 route integration", () => {
  it("mounts latest-revision downloads from the read-only review", () => {
    const text = source("./transcription-review.tsx");
    expect(text).toContain("LatestRevisionArtifactDownloads");
  });

  it("mounts concrete revision downloads from the editor", () => {
    const text = source("./transcription-revision-editor.tsx");
    expect(text).toContain("RevisionArtifactDownloads");
    expect(text).toContain("revisionNumber={serverRevision.revision_number}");
  });

  it("mounts concrete latest revision downloads from synchronized playback", () => {
    const text = source("./transcription-synchronized-playback.tsx");
    expect(text).toContain("RevisionArtifactDownloads");
    expect(text).toContain("revisionNumber={revision.revision_number}");
  });

  it("does not expose PDF, FastAPI, direct storage URLs, or window.open", () => {
    const combined = [
      source("./revision-artifact-downloads.tsx"),
      source("../lib/transcription-artifacts.ts"),
      source("../lib/download-blob.ts"),
    ].join("\n");
    expect(combined).not.toMatch(/pdf/i);
    expect(combined).not.toContain("8000");
    expect(combined).not.toContain("window.open");
    expect(combined).not.toContain("localStorage");
    expect(combined).not.toContain("indexedDB");
  });
});
