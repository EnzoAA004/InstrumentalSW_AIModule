import { describe, expect, it, vi } from "vitest";

import { downloadRevisionArtifact } from "./transcription-artifacts";

const JOB_ID = "11111111-1111-1111-1111-111111111111";
const BYTES = new Uint8Array([1, 2, 3, 4]);
const SHA = "9f64a747e1b97f131fabb6b447296c9b6f0201e79fb3c5356e6c77e89b6a806a";

function metadata() {
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
    ],
  };
}

function digestProvider(hex = SHA): Crypto {
  const result = new ArrayBuffer(32);
  const view = new Uint8Array(result);
  for (let index = 0; index < 32; index += 1)
    view[index] = Number.parseInt(hex.slice(index * 2, index * 2 + 2), 16);
  return { subtle: { digest: vi.fn().mockResolvedValue(result) } } as unknown as Crypto;
}

describe("downloadRevisionArtifact", () => {
  it("downloads through Spring, verifies bytes, and returns a typed Blob result", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(metadata()), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(BYTES, {
          status: 200,
          headers: {
            "Content-Type": "audio/midi",
            "Content-Disposition": 'attachment; filename="transcription-r2.mid"',
            "Content-Length": "4",
            "X-Content-SHA256": SHA,
          },
        }),
      );

    const result = await downloadRevisionArtifact(JOB_ID, 2, "midi", undefined, digestProvider());

    expect(result).toMatchObject({
      filename: "transcription-r2.mid",
      mediaType: "audio/midi",
      sizeBytes: 4,
      sha256: SHA,
    });
    expect(result.blob).toBeInstanceOf(Blob);
    expect(result.blob.type).toBe("audio/midi");
    expect(new Uint8Array(await result.blob.arrayBuffer())).toEqual(BYTES);
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      `http://localhost:8080/api/v1/transcriptions/${JOB_ID}/revisions/2/artifacts/midi`,
    );
    expect(JSON.stringify(fetchMock.mock.calls)).not.toContain("8000");
  });

  it.each([
    ["size", "5", SHA, digestProvider()],
    ["header hash", "4", "0".repeat(64), digestProvider()],
    ["calculated hash", "4", SHA, digestProvider("0".repeat(64))],
  ])(
    "rejects incompatible %s without returning a Blob",
    async (_name, length, headerSha, crypto) => {
      vi.spyOn(globalThis, "fetch")
        .mockResolvedValueOnce(new Response(JSON.stringify(metadata()), { status: 200 }))
        .mockResolvedValueOnce(
          new Response(BYTES, {
            status: 200,
            headers: {
              "Content-Type": "audio/midi",
              "Content-Disposition": 'attachment; filename="transcription-r2.mid"',
              "Content-Length": length,
              "X-Content-SHA256": headerSha,
            },
          }),
        );

      await expect(
        downloadRevisionArtifact(JOB_ID, 2, "midi", undefined, crypto),
      ).rejects.toMatchObject({
        code: "INVALID_BACKEND_RESPONSE",
      });
    },
  );

  it("rejects unsafe or mismatched Content-Disposition filenames", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(metadata()), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(BYTES, {
          status: 200,
          headers: {
            "Content-Type": "audio/midi",
            "Content-Disposition": 'attachment; filename="../x.mid"',
            "Content-Length": "4",
            "X-Content-SHA256": SHA,
          },
        }),
      );
    await expect(
      downloadRevisionArtifact(JOB_ID, 2, "midi", undefined, digestProvider()),
    ).rejects.toMatchObject({
      code: "INVALID_BACKEND_RESPONSE",
    });
  });
});
