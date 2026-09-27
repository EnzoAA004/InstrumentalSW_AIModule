import { afterEach, describe, expect, it, vi } from "vitest";

import { downloadRevisionArtifact, getRevisionArtifacts } from "./transcription-artifacts";

const JOB_ID = "11111111-1111-1111-1111-111111111111";
const SHA = "9f64a747e1b97f131fabb6b447296c9b6f0201e79fb3c5356e6c77e89b6a806a";
const BYTES = new Uint8Array([1, 2, 3, 4]);

function descriptor(overrides: Record<string, unknown> = {}) {
  return {
    artifact_id: "midi",
    artifact_type: "midi",
    filename: "transcription-r2.mid",
    media_type: "audio/midi",
    extension: ".mid",
    size_bytes: 4,
    sha256: SHA,
    order: 0,
    ...overrides,
  };
}

function listing(overrides: Record<string, unknown> = {}) {
  return {
    job_id: JOB_ID,
    revision_number: 2,
    artifacts: [descriptor()],
    ...overrides,
  };
}

function arrayBuffer(bytes: Uint8Array): ArrayBuffer {
  const result = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(result).set(bytes);
  return result;
}

function digestProvider(): Crypto {
  const digest = Uint8Array.from(SHA.match(/.{2}/g) ?? [], (value) => Number.parseInt(value, 16));
  return {
    subtle: { digest: vi.fn().mockResolvedValue(arrayBuffer(digest)) },
  } as unknown as Crypto;
}

function metadataResponse(body: unknown = listing(), status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

function binaryResponse(headers: Record<string, string> = {}): Response {
  return new Response(arrayBuffer(BYTES), {
    status: 200,
    headers: {
      "Content-Type": "audio/midi",
      "Content-Disposition": 'attachment; filename="transcription-r2.mid"',
      "X-Content-SHA256": SHA,
      ...headers,
    },
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  delete process.env.NEXT_PUBLIC_SAXO_API_BASE_URL;
});

describe("artifact client coverage", () => {
  it("rejects invalid job, revision, and artifact identities before network access", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    await expect(getRevisionArtifacts("invalid", 0)).rejects.toMatchObject({
      code: "INVALID_JOB_ID",
    });
    await expect(getRevisionArtifacts(JOB_ID, -1)).rejects.toMatchObject({
      code: "REVISION_NOT_FOUND",
    });
    await expect(downloadRevisionArtifact(JOB_ID, 0, "../midi")).rejects.toMatchObject({
      code: "INVALID_BACKEND_RESPONSE",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("uses configured Backend URL and accepts absent optional Content-Length", async () => {
    process.env.NEXT_PUBLIC_SAXO_API_BASE_URL = "http://product-api///";
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(metadataResponse())
      .mockResolvedValueOnce(binaryResponse());

    await expect(
      downloadRevisionArtifact(JOB_ID, 2, "midi", undefined, digestProvider()),
    ).resolves.toMatchObject({ filename: "transcription-r2.mid" });
    expect(fetchMock.mock.calls[0]?.[0]).toContain("http://product-api/api/v1/");
  });

  it("returns stable missing-artifact and unavailable-Web-Crypto errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(metadataResponse());
    await expect(downloadRevisionArtifact(JOB_ID, 2, "svg-page-001")).rejects.toMatchObject({
      code: "ARTIFACT_NOT_FOUND",
    });

    vi.restoreAllMocks();
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(metadataResponse())
      .mockResolvedValueOnce(binaryResponse({ "Content-Length": "4" }));
    await expect(
      downloadRevisionArtifact(JOB_ID, 2, "midi", undefined, {} as Crypto),
    ).rejects.toMatchObject({ code: "WEB_CRYPTO_UNAVAILABLE" });
  });

  it("maps public binary errors and rejects malformed error envelopes", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(metadataResponse())
      .mockResolvedValueOnce(
        metadataResponse(
          { code: "ARTIFACT_NOT_FOUND", message: "Not found.", field: "artifact_id" },
          404,
        ),
      );
    await expect(downloadRevisionArtifact(JOB_ID, 2, "midi")).rejects.toMatchObject({
      code: "ARTIFACT_NOT_FOUND",
    });

    vi.restoreAllMocks();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      metadataResponse({ message: "missing code" }, 500),
    );
    await expect(getRevisionArtifacts(JOB_ID, 2)).rejects.toMatchObject({
      code: "INVALID_BACKEND_RESPONSE",
    });
  });

  it("preserves abort rejection and maps ordinary network rejection", async () => {
    const controller = new AbortController();
    controller.abort();
    const aborted = new DOMException("aborted", "AbortError");
    vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(aborted);
    await expect(getRevisionArtifacts(JOB_ID, 2, controller.signal)).rejects.toBe(aborted);

    vi.restoreAllMocks();
    vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("private network"));
    await expect(getRevisionArtifacts(JOB_ID, 2)).rejects.toMatchObject({
      code: "BACKEND_UNAVAILABLE",
    });
  });

  it.each([
    ["non-object", null],
    ["non-array", { ...listing(), artifacts: {} }],
    ["extra field", { ...listing(), unexpected: true }],
    ["job mismatch", listing({ job_id: "22222222-2222-2222-2222-222222222222" })],
    ["revision mismatch", listing({ revision_number: 3 })],
    ["empty", listing({ artifacts: [] })],
    ["non-object descriptor", listing({ artifacts: [null] })],
    ["extra descriptor field", listing({ artifacts: [{ ...descriptor(), extra: true }] })],
    ["invalid ID", listing({ artifacts: [descriptor({ artifact_id: "bad/id" })] })],
    ["invalid type", listing({ artifacts: [descriptor({ artifact_type: "pdf" })] })],
    ["invalid filename type", listing({ artifacts: [descriptor({ filename: 7 })] })],
    ["hidden filename", listing({ artifacts: [descriptor({ filename: ".hidden.mid" })] })],
    ["backslash filename", listing({ artifacts: [descriptor({ filename: "folder\\x.mid" })] })],
    ["missing media type", listing({ artifacts: [descriptor({ media_type: null })] })],
    ["missing extension", listing({ artifacts: [descriptor({ extension: null })] })],
    ["fractional size", listing({ artifacts: [descriptor({ size_bytes: 4.5 })] })],
    ["zero size", listing({ artifacts: [descriptor({ size_bytes: 0 })] })],
    ["invalid SHA", listing({ artifacts: [descriptor({ sha256: "A".repeat(64) })] })],
    ["wrong order", listing({ artifacts: [descriptor({ order: 1 })] })],
    ["wrong extension", listing({ artifacts: [descriptor({ extension: ".svg" })] })],
    ["wrong filename extension", listing({ artifacts: [descriptor({ filename: "score.svg" })] })],
    [
      "duplicate filename",
      listing({
        artifacts: [
          descriptor(),
          descriptor({ artifact_id: "copy", artifact_type: "midi", order: 1 }),
        ],
      }),
    ],
  ])("rejects incompatible metadata: %s", async (_name, body) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(metadataResponse(body));
    await expect(getRevisionArtifacts(JOB_ID, 2)).rejects.toMatchObject({
      code: "INVALID_BACKEND_RESPONSE",
    });
  });

  it("rejects invalid JSON and incompatible binary content type", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response("not-json", { status: 200 }));
    await expect(getRevisionArtifacts(JOB_ID, 2)).rejects.toMatchObject({
      code: "INVALID_BACKEND_RESPONSE",
    });

    vi.restoreAllMocks();
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(metadataResponse())
      .mockResolvedValueOnce(binaryResponse({ "Content-Type": "image/svg+xml" }));
    await expect(
      downloadRevisionArtifact(JOB_ID, 2, "midi", undefined, digestProvider()),
    ).rejects.toMatchObject({ code: "INVALID_BACKEND_RESPONSE" });
  });
});
