import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getTranscriptionReview,
  TranscriptionApiError,
  type TranscriptionReview,
} from "./transcription-api";

const JOB_ID = "11111111-1111-1111-1111-111111111111";
const REVIEW: TranscriptionReview = {
  job_id: JOB_ID,
  schema_version: "1.0",
  note_event_schema_version: "1.0",
  low_confidence_policy_version: "1.0",
  written_pitch_policy_version: "1.0",
  saxophone_type: "alto",
  low_confidence_threshold: 0.5,
  confidence_interpretation: "model_signal_not_calibrated_accuracy",
  confidence_method: "model_probability",
  summary: { event_count: 2, low_confidence_count: 1 },
  events: [
    {
      index: 0,
      pitch_concert_midi: 60,
      written_pitch_midi: 69,
      onset_seconds: 0,
      offset_seconds: 0.5,
      velocity: 90,
      confidence: 0.42,
      is_low_confidence: true,
    },
    {
      index: 1,
      pitch_concert_midi: 67,
      written_pitch_midi: 76,
      onset_seconds: 0.25,
      offset_seconds: 1,
      velocity: 100,
      confidence: 0.82,
      is_low_confidence: false,
    },
  ],
};

function response(status: number, body: unknown): Response {
  return new Response(typeof body === "string" ? body : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("getTranscriptionReview", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.NEXT_PUBLIC_SAXO_API_BASE_URL;
  });

  it("gets the exact Backend URL once without body or polling", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(200, REVIEW));
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();

    await expect(getTranscriptionReview(JOB_ID, controller.signal)).resolves.toEqual(REVIEW);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8080/api/v1/transcriptions/${JOB_ID}/review`,
      { method: "GET", signal: controller.signal },
    );
    expect(String(fetchMock.mock.calls[0]?.[0])).not.toContain("localhost:8000");
  });

  it("rejects an invalid UUID before fetch", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(getTranscriptionReview("../bad")).rejects.toMatchObject({
      code: "INVALID_JOB_ID",
      status: 400,
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    [400, "INVALID_JOB_ID"],
    [404, "TRANSCRIPTION_NOT_FOUND"],
    [409, "TRANSCRIPTION_RESULT_NOT_READY"],
    [502, "AI_SERVICE_ERROR"],
  ])("maps public %i envelopes", async (status, code) => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          response(status, { code, message: "Readable public message.", field: "job_id" }),
        ),
    );

    await expect(getTranscriptionReview(JOB_ID)).rejects.toMatchObject({ code, status });
  });

  it.each([
    "not-json",
    JSON.stringify({ ...REVIEW, job_id: "22222222-2222-2222-2222-222222222222" }),
    JSON.stringify({ ...REVIEW, schema_version: "2.0" }),
    JSON.stringify({ ...REVIEW, summary: { event_count: 9, low_confidence_count: 1 } }),
    JSON.stringify({ ...REVIEW, events: [{ ...REVIEW.events[0], index: 2 }] }),
    JSON.stringify({ ...REVIEW, events: [{ ...REVIEW.events[0], confidence: 2 }] }),
  ])("rejects incompatible HTTP 200 JSON", async (body) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(200, body)));

    await expect(getTranscriptionReview(JOB_ID)).rejects.toMatchObject({
      code: "INVALID_BACKEND_RESPONSE",
      status: 200,
    });
  });

  it("maps network failure safely and preserves abort", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValueOnce(new TypeError("private")));
    await expect(getTranscriptionReview(JOB_ID)).rejects.toMatchObject({
      code: "BACKEND_UNAVAILABLE",
    });

    const controller = new AbortController();
    controller.abort();
    const aborted = new DOMException("Aborted", "AbortError");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValueOnce(aborted));
    await expect(getTranscriptionReview(JOB_ID, controller.signal)).rejects.toBe(aborted);
  });

  it("uses typed public errors", () => {
    expect(new TranscriptionApiError("X", "message", null, 409)).toMatchObject({ status: 409 });
  });
});
