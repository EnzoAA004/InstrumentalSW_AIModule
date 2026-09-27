import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getTranscription,
  TranscriptionApiError,
  type TranscriptionJob,
} from "./transcription-api";

const JOB_ID = "11111111-1111-1111-1111-111111111111";
const SUCCESS: TranscriptionJob = {
  job_id: JOB_ID,
  status: "UPLOADED",
  filename: "take.wav",
  size_bytes: 15,
  audio_sha256: "a".repeat(64),
  saxophone_type: "alto",
  input_mode: "solo",
};

function response(status: number, body: unknown): Response {
  return new Response(typeof body === "string" ? body : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("getTranscription", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.NEXT_PUBLIC_SAXO_API_BASE_URL;
  });

  it("gets the exact UUID from the product Backend without multipart or a request body", async () => {
    process.env.NEXT_PUBLIC_SAXO_API_BASE_URL = "http://localhost:8080/";
    const fetchMock = vi.fn().mockResolvedValue(response(200, SUCCESS));
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();

    await expect(getTranscription(JOB_ID, controller.signal)).resolves.toEqual(SUCCESS);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8080/api/v1/transcriptions/${JOB_ID}`,
      {
        method: "GET",
        signal: controller.signal,
      },
    );
    expect(String(fetchMock.mock.calls[0]?.[0])).not.toContain("localhost:8000");
  });

  it("rejects an invalid UUID before fetch", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(getTranscription("../not-a-uuid")).rejects.toMatchObject({
      code: "INVALID_JOB_ID",
      status: 400,
      field: "job_id",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("encodes the validated identifier in the URL and uses the local Backend fallback", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(200, SUCCESS));
    vi.stubGlobal("fetch", fetchMock);

    await getTranscription(JOB_ID);

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      `http://localhost:8080/api/v1/transcriptions/${encodeURIComponent(JOB_ID)}`,
    );
  });

  it.each([
    [400, "INVALID_JOB_ID"],
    [404, "TRANSCRIPTION_NOT_FOUND"],
    [502, "AI_SERVICE_ERROR"],
  ])("maps public %i envelopes", async (status, code) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response(status, {
          code,
          message: "Readable public message.",
          field: "job_id",
        }),
      ),
    );

    await expect(getTranscription(JOB_ID)).rejects.toMatchObject({
      name: "TranscriptionApiError",
      code,
      message: "Readable public message.",
      field: "job_id",
      status,
    });
  });

  it("maps a rejected network request without exposing its detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("private network detail")));

    await expect(getTranscription(JOB_ID)).rejects.toMatchObject({
      code: "BACKEND_UNAVAILABLE",
      message: "The Saxo service is currently unavailable. Try again.",
      status: null,
    });
  });

  it("preserves an explicit abort instead of converting it to a network error", async () => {
    const controller = new AbortController();
    const aborted = new DOMException("The operation was aborted.", "AbortError");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async () => {
        controller.abort();
        throw aborted;
      }),
    );

    await expect(getTranscription(JOB_ID, controller.signal)).rejects.toBe(aborted);
  });

  it("rejects a valid but different response UUID", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          response(200, { ...SUCCESS, job_id: "22222222-2222-2222-2222-222222222222" }),
        ),
    );

    await expect(getTranscription(JOB_ID)).rejects.toMatchObject({
      code: "INVALID_BACKEND_RESPONSE",
      status: 200,
    });
  });

  it.each([
    "not-json",
    JSON.stringify({ ...SUCCESS, job_id: "not-a-uuid" }),
    JSON.stringify({ ...SUCCESS, audio_sha256: "ABC" }),
    JSON.stringify({ ...SUCCESS, size_bytes: -1 }),
    JSON.stringify({ ...SUCCESS, filename: "C:\\private\\take.wav" }),
    JSON.stringify({ ...SUCCESS, saxophone_type: "clarinet" }),
    JSON.stringify({ ...SUCCESS, input_mode: "stream" }),
    JSON.stringify({ ...SUCCESS, status: "" }),
  ])("rejects incompatible HTTP 200 JSON", async (body) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(200, body)));

    await expect(getTranscription(JOB_ID)).rejects.toMatchObject({
      code: "INVALID_BACKEND_RESPONSE",
      status: 200,
    });
  });

  it("requires HTTP 200 even when another status has a compatible job", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(202, SUCCESS)));

    await expect(getTranscription(JOB_ID)).rejects.toBeInstanceOf(TranscriptionApiError);
  });
});
