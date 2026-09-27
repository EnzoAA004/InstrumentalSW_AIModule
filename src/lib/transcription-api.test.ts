import { afterEach, describe, expect, it, vi } from "vitest";

import {
  TranscriptionApiError,
  submitTranscription,
  type TranscriptionJob,
} from "./transcription-api";

const SUCCESS: TranscriptionJob = {
  job_id: "11111111-1111-1111-1111-111111111111",
  status: "UPLOADED",
  filename: "take.wav",
  size_bytes: 15,
  audio_sha256: "a".repeat(64),
  saxophone_type: "alto",
  input_mode: "solo",
};

function audio(name = "take.wav", content = "synthetic-audio") {
  return new File([content], name, { type: "audio/wav" });
}

function response(status: number, body: unknown): Response {
  return new Response(typeof body === "string" ? body : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("submitTranscription", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.NEXT_PUBLIC_SAXO_API_BASE_URL;
  });

  it("posts exact multipart fields to the product Backend without a manual content type", async () => {
    process.env.NEXT_PUBLIC_SAXO_API_BASE_URL = "http://localhost:8080/";
    const fetchMock = vi.fn().mockResolvedValue(response(202, SUCCESS));
    vi.stubGlobal("fetch", fetchMock);
    const file = audio();

    await expect(
      submitTranscription({ file, saxophoneType: "alto", inputMode: "solo" }),
    ).resolves.toEqual(SUCCESS);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8080/api/v1/transcriptions");
    expect(init.method).toBe("POST");
    expect(init.headers).toBeUndefined();
    expect(init.body).toBeInstanceOf(FormData);
    const form = init.body as FormData;
    expect([...form.keys()]).toEqual(["file", "saxophone_type", "input_mode"]);
    expect(form.get("file")).toBe(file);
    expect(form.get("saxophone_type")).toBe("alto");
    expect(form.get("input_mode")).toBe("solo");
  });

  it("uses the documented local Backend URL when the environment value is absent", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(202, SUCCESS));
    vi.stubGlobal("fetch", fetchMock);

    await submitTranscription({
      file: audio(),
      saxophoneType: "baritone",
      inputMode: "mixture",
    });

    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://localhost:8080/api/v1/transcriptions");
    const form = (fetchMock.mock.calls[0]?.[1] as RequestInit).body as FormData;
    expect(form.get("saxophone_type")).toBe("baritone");
    expect(form.get("input_mode")).toBe("mixture");
  });

  it.each([
    [400, "INVALID_TRANSCRIPTION_REQUEST"],
    [413, "AUDIO_SIZE_LIMIT_EXCEEDED"],
    [415, "UNSUPPORTED_AUDIO_FORMAT"],
    [422, "INVALID_TRANSCRIPTION_REQUEST"],
    [502, "AI_SERVICE_UNAVAILABLE"],
  ])("maps public %i errors without exposing raw response bodies", async (status, code) => {
    const fetchMock = vi.fn().mockResolvedValue(
      response(status, {
        code,
        message: "Readable public message.",
        field: status === 413 || status === 415 ? "file" : null,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      submitTranscription({ file: audio(), saxophoneType: "alto", inputMode: "solo" }),
    ).rejects.toMatchObject({
      name: "TranscriptionApiError",
      code,
      message: "Readable public message.",
      field: status === 413 || status === 415 ? "file" : null,
      status,
    });
  });

  it("uses a stable unavailable error for rejected network requests", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("private network detail")));

    await expect(
      submitTranscription({ file: audio(), saxophoneType: "alto", inputMode: "solo" }),
    ).rejects.toEqual(
      expect.objectContaining({
        code: "BACKEND_UNAVAILABLE",
        message: "The Saxo service is currently unavailable. Try again.",
      }),
    );
  });

  it.each([
    "not-json",
    JSON.stringify({ ...SUCCESS, job_id: "not-a-uuid" }),
    JSON.stringify({ ...SUCCESS, audio_sha256: "ABC" }),
    JSON.stringify({ ...SUCCESS, size_bytes: -1 }),
    JSON.stringify({ ...SUCCESS, saxophone_type: "clarinet" }),
    JSON.stringify({ ...SUCCESS, input_mode: "stream" }),
  ])("rejects incompatible success JSON as a stable response error", async (body) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(202, body)));

    await expect(
      submitTranscription({ file: audio(), saxophoneType: "alto", inputMode: "solo" }),
    ).rejects.toMatchObject({
      code: "INVALID_BACKEND_RESPONSE",
      message: "The Saxo service returned an invalid response.",
    });
  });

  it("requires HTTP 202 even when another success status has a compatible body", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(200, SUCCESS)));

    await expect(
      submitTranscription({ file: audio(), saxophoneType: "alto", inputMode: "solo" }),
    ).rejects.toBeInstanceOf(TranscriptionApiError);
  });
});
