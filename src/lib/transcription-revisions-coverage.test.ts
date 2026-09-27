import { afterEach, describe, expect, it, vi } from "vitest";

import { TranscriptionApiError } from "./transcription-api";
import {
  buildRevisionOperations,
  createTranscriptionRevision,
  getTranscriptionRevision,
  getTranscriptionRevisionHistory,
  requestArtifactRegeneration,
  revisionToDraftEvents,
  validateDraftEvents,
  type DraftRevisionEvent,
  type TranscriptionRevision,
} from "./transcription-revisions";

const JOB_ID = "11111111-1111-1111-1111-111111111111";
const REVISION: TranscriptionRevision = {
  job_id: JOB_ID,
  revision_number: 0,
  parent_revision_number: null,
  created_at: "2026-07-22T11:00:00Z",
  saxophone_type: "alto",
  events: [
    {
      event_id: "source-0",
      origin: "model",
      source_index: 0,
      pitch_concert_midi: 60,
      written_pitch_midi: 69,
      onset_seconds: 0,
      offset_seconds: 0.5,
      velocity: 90,
      confidence: 0.42,
      is_low_confidence: true,
    },
  ],
  summary: { event_count: 1, model_event_count: 1, human_event_count: 0 },
  derived_artifacts_status: "CURRENT",
  schema_version: "1.0",
};

function response(status: number, body: unknown): Response {
  return new Response(typeof body === "string" ? body : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  delete process.env.NEXT_PUBLIC_SAXO_API_BASE_URL;
});

describe("revision client defensive branches", () => {
  it("rejects malformed identifiers and revision numbers before fetch", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(getTranscriptionRevisionHistory("bad")).rejects.toMatchObject({
      code: "INVALID_JOB_ID",
      status: 400,
    });
    await expect(getTranscriptionRevision(JOB_ID, -1)).rejects.toMatchObject({
      code: "REVISION_NOT_FOUND",
      status: 404,
    });
    await expect(requestArtifactRegeneration(JOB_ID, 1.2)).rejects.toMatchObject({
      code: "REVISION_NOT_FOUND",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("maps network failure and preserves abort", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValueOnce(new TypeError("private")));
    await expect(getTranscriptionRevisionHistory(JOB_ID)).rejects.toMatchObject({
      code: "BACKEND_UNAVAILABLE",
    });

    const controller = new AbortController();
    controller.abort();
    const aborted = new DOMException("Aborted", "AbortError");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValueOnce(aborted));
    await expect(getTranscriptionRevisionHistory(JOB_ID, controller.signal)).rejects.toBe(aborted);
  });

  it("rejects malformed JSON and non-public error envelopes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(200, "not-json")));
    await expect(getTranscriptionRevisionHistory(JOB_ID)).rejects.toMatchObject({
      code: "INVALID_BACKEND_RESPONSE",
    });

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(500, { detail: "private" })));
    await expect(getTranscriptionRevisionHistory(JOB_ID)).rejects.toMatchObject({
      code: "INVALID_BACKEND_RESPONSE",
      status: 500,
    });
  });

  it("rejects empty commands before POST", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      createTranscriptionRevision(JOB_ID, { base_revision_number: 0, operations: [] }),
    ).rejects.toMatchObject({ code: "INVALID_REVISION_OPERATION", status: 422 });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("draft validation defensive branches", () => {
  const base = revisionToDraftEvents(REVISION)[0]!;

  it("reports empty velocity offset and invalid origin or identity", () => {
    const drafts = [
      { ...base, event_id: "", origin: "other" as "model", velocity: "" },
      {
        ...base,
        event_id: "source-1",
        source_index: 1,
        onset_seconds: "0",
        offset_seconds: "",
      },
    ];
    const result = validateDraftEvents(drafts, "alto");
    expect(result.errors[".event_id"]).toBe("Event ID is required.");
    expect(result.errors[".origin"]).toBe("Event origin is invalid.");
    expect(result.errors[".velocity"]).toBe("Velocity is required.");
    expect(result.errors["source-1.offset_seconds"]).toBe("Offset is required.");
  });

  it("reports non-finite times and invalid velocity text", () => {
    const draft: DraftRevisionEvent = {
      ...base,
      onset_seconds: "Infinity",
      offset_seconds: "NaN",
      velocity: "x",
    };
    const result = validateDraftEvents([draft], "alto");
    expect(result.errors["source-0.onset_seconds"]).toContain("finite");
    expect(result.errors["source-0.offset_seconds"]).toContain("finite");
    expect(result.errors["source-0.velocity"]).toContain("integer");
  });

  it("builds no operations for an unchanged revision and throws for invalid drafts", () => {
    expect(buildRevisionOperations(REVISION, revisionToDraftEvents(REVISION))).toEqual([]);
    expect(() =>
      buildRevisionOperations(REVISION, [{ ...base, written_pitch_midi: "200" }]),
    ).toThrow(TranscriptionApiError);
  });

  it("builds update delete and append operations deterministically", () => {
    const human: DraftRevisionEvent = {
      event_id: "draft-human-1",
      origin: "human",
      source_index: null,
      written_pitch_midi: "72",
      onset_seconds: "0.7",
      offset_seconds: "1",
      velocity: "64",
      confidence: null,
      is_low_confidence: null,
    };
    const updated = { ...base, written_pitch_midi: "70", onset_seconds: "0.1" };
    expect(buildRevisionOperations(REVISION, [updated, human])).toEqual([
      {
        type: "update",
        event_id: "source-0",
        written_pitch_midi: 70,
        onset_seconds: 0.1,
        offset_seconds: 0.5,
      },
      {
        type: "add",
        written_pitch_midi: 72,
        onset_seconds: 0.7,
        offset_seconds: 1,
        velocity: 64,
      },
    ]);
    expect(buildRevisionOperations(REVISION, [])).toEqual([
      { type: "delete", event_id: "source-0" },
    ]);
  });
});
