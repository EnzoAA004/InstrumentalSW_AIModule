import { describe, expect, it, vi } from "vitest";

import {
  TranscriptionArtifactError,
  getRevisionArtifacts,
  type RevisionArtifactList,
} from "./transcription-artifacts";

const JOB_ID = "11111111-1111-1111-1111-111111111111";
const SHA = "9f64a747e1b97f131fabb6b447296c9b6f0201e79fb3c5356e6c77e89b6a806a";

function payload(): RevisionArtifactList {
  return {
    job_id: JOB_ID,
    revision_number: 2,
    artifacts: [
      {
        artifact_id: "midi",
        artifact_type: "midi",
        filename: "transcription-r2.mid",
        media_type: "audio/midi",
        extension: ".mid",
        size_bytes: 4,
        sha256: SHA,
        order: 0,
      },
      {
        artifact_id: "musicxml",
        artifact_type: "musicxml",
        filename: "transcription-r2.musicxml",
        media_type: "application/vnd.recordare.musicxml+xml",
        extension: ".musicxml",
        size_bytes: 10,
        sha256: "a".repeat(64),
        order: 1,
      },
      {
        artifact_id: "svg-page-001",
        artifact_type: "svg",
        filename: "transcription-r2-page-001.svg",
        media_type: "image/svg+xml",
        extension: ".svg",
        size_bytes: 20,
        sha256: "b".repeat(64),
        order: 2,
      },
    ],
  };
}

describe("getRevisionArtifacts", () => {
  it("calls only Spring with a bodyless GET and validates complete metadata", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(payload()), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(getRevisionArtifacts(JOB_ID, 2)).resolves.toEqual(payload());
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8080/api/v1/transcriptions/${JOB_ID}/revisions/2/artifacts`,
      { method: "GET", signal: undefined },
    );
    expect(JSON.stringify(fetchMock.mock.calls)).not.toContain("8000");
  });

  it.each([
    [
      "duplicate order",
      { ...payload(), artifacts: [payload().artifacts[0], payload().artifacts[0]] },
    ],
    ["PDF", { ...payload(), artifacts: [{ ...payload().artifacts[0], artifact_type: "pdf" }] }],
    [
      "unsafe filename",
      { ...payload(), artifacts: [{ ...payload().artifacts[0], filename: "../x.mid" }] },
    ],
    [
      "wrong media",
      { ...payload(), artifacts: [{ ...payload().artifacts[0], media_type: "image/svg+xml" }] },
    ],
  ])("rejects incompatible %s metadata", async (_name, body) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(body), { status: 200 }),
    );
    await expect(getRevisionArtifacts(JOB_ID, 2)).rejects.toMatchObject({
      code: "INVALID_BACKEND_RESPONSE",
    });
  });

  it("maps not-ready and public errors without raw payload leakage", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          code: "ARTIFACTS_NOT_READY",
          message: "Artifacts are not available for this revision yet.",
          field: "revision_number",
        }),
        { status: 409 },
      ),
    );
    await expect(getRevisionArtifacts(JOB_ID, 2)).rejects.toEqual(
      new TranscriptionArtifactError(
        "ARTIFACTS_NOT_READY",
        "Artifacts are not available for this revision yet.",
        "revision_number",
        409,
      ),
    );
  });
});
