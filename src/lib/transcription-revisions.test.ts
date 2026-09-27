import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createTranscriptionRevision,
  getTranscriptionRevision,
  getTranscriptionRevisionHistory,
  requestArtifactRegeneration,
  validateDraftEvents,
  type DraftRevisionEvent,
  type TranscriptionRevision,
  type TranscriptionRevisionHistory,
} from "./transcription-revisions";

const JOB_ID = "11111111-1111-1111-1111-111111111111";

const REVISION: TranscriptionRevision = {
  job_id: JOB_ID,
  revision_number: 1,
  parent_revision_number: 0,
  created_at: "2026-07-22T12:00:00Z",
  saxophone_type: "alto",
  events: [
    {
      event_id: "source-0",
      origin: "model",
      source_index: 0,
      pitch_concert_midi: 61,
      written_pitch_midi: 70,
      onset_seconds: 0.1,
      offset_seconds: 0.6,
      velocity: 90,
      confidence: 0.42,
      is_low_confidence: true,
    },
    {
      event_id: "human-22222222-2222-2222-2222-222222222222",
      origin: "human",
      source_index: null,
      pitch_concert_midi: 63,
      written_pitch_midi: 72,
      onset_seconds: 0.7,
      offset_seconds: 1,
      velocity: 64,
      confidence: null,
      is_low_confidence: null,
    },
  ],
  summary: { event_count: 2, model_event_count: 1, human_event_count: 1 },
  derived_artifacts_status: "STALE",
  schema_version: "1.0",
};

const HISTORY: TranscriptionRevisionHistory = {
  job_id: JOB_ID,
  latest_revision_number: 1,
  revision_count: 2,
  revisions: [
    {
      revision_number: 0,
      parent_revision_number: null,
      created_at: "2026-07-22T11:00:00Z",
      event_count: 2,
      model_event_count: 2,
      human_event_count: 0,
      derived_artifacts_status: "CURRENT",
    },
    {
      revision_number: 1,
      parent_revision_number: 0,
      created_at: "2026-07-22T12:00:00Z",
      event_count: 2,
      model_event_count: 1,
      human_event_count: 1,
      derived_artifacts_status: "STALE",
    },
  ],
};

function response(status: number, body: unknown): Response {
  return new Response(typeof body === "string" ? body : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("transcription revision API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.NEXT_PUBLIC_SAXO_API_BASE_URL;
  });

  it("loads history and exact revision through Backend only", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(200, HISTORY))
      .mockResolvedValueOnce(response(200, REVISION));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getTranscriptionRevisionHistory(JOB_ID)).resolves.toEqual(HISTORY);
    await expect(getTranscriptionRevision(JOB_ID, 1)).resolves.toEqual(REVISION);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `http://localhost:8080/api/v1/transcriptions/${JOB_ID}/revisions`,
      { method: "GET", signal: undefined },
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `http://localhost:8080/api/v1/transcriptions/${JOB_ID}/revisions/1`,
      { method: "GET", signal: undefined },
    );
    expect(String(fetchMock.mock.calls[0]?.[0])).not.toContain("localhost:8000");
  });

  it("sends one exact revision POST without autosave or polling", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(201, REVISION));
    vi.stubGlobal("fetch", fetchMock);
    const command = {
      base_revision_number: 0,
      operations: [
        {
          type: "update" as const,
          event_id: "source-0",
          written_pitch_midi: 70,
          onset_seconds: 0.1,
          offset_seconds: 0.6,
        },
        {
          type: "add" as const,
          written_pitch_midi: 72,
          onset_seconds: 0.7,
          offset_seconds: 1,
          velocity: 64,
        },
        { type: "delete" as const, event_id: "source-1" },
      ],
    };

    await expect(createTranscriptionRevision(JOB_ID, command)).resolves.toEqual(REVISION);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8080/api/v1/transcriptions/${JOB_ID}/revisions`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(command),
        signal: undefined,
      },
    );
  });

  it("requests regeneration explicitly and accepts only REQUESTED", async () => {
    const request = {
      request_id: "33333333-3333-3333-3333-333333333333",
      job_id: JOB_ID,
      revision_number: 1,
      status: "REQUESTED" as const,
      requested_artifacts: ["midi", "musicxml", "svg"] as const,
    };
    const fetchMock = vi.fn().mockResolvedValue(response(202, request));
    vi.stubGlobal("fetch", fetchMock);

    await expect(requestArtifactRegeneration(JOB_ID, 1)).resolves.toEqual(request);
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8080/api/v1/transcriptions/${JOB_ID}/revisions/1/regeneration-requests`,
      { method: "POST", signal: undefined },
    );
    expect(JSON.stringify(request)).not.toMatch(/completed|bytes|progress|eta/i);
  });

  it.each([
    [400, "INVALID_JOB_ID"],
    [404, "REVISION_NOT_FOUND"],
    [409, "TRANSCRIPTION_RESULT_NOT_READY"],
    [409, "REVISION_CONFLICT"],
    [422, "INVALID_REVISION_OPERATION"],
    [502, "AI_SERVICE_ERROR"],
  ])("preserves stable public %i %s errors", async (status, code) => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          response(status, { code, message: "Readable public message.", field: "operations" }),
        ),
    );
    await expect(getTranscriptionRevisionHistory(JOB_ID)).rejects.toMatchObject({ code, status });
  });

  it("rejects incompatible successful history revision and request payloads", async () => {
    const invalidPayloads = [
      { ...HISTORY, latest_revision_number: 3 },
      { ...REVISION, summary: { event_count: 9, model_event_count: 1, human_event_count: 1 } },
      { ...REVISION, events: [{ ...REVISION.events[0], event_id: "human-bad", origin: "human" }] },
      {
        request_id: "33333333-3333-3333-3333-333333333333",
        job_id: JOB_ID,
        revision_number: 1,
        status: "COMPLETED",
        requested_artifacts: ["midi", "musicxml", "svg"],
      },
    ];
    for (const payload of invalidPayloads) {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(200, payload)));
      await expect(getTranscriptionRevisionHistory(JOB_ID)).rejects.toMatchObject({
        code: "INVALID_BACKEND_RESPONSE",
      });
    }
  });
});

describe("validateDraftEvents", () => {
  const valid: DraftRevisionEvent[] = [
    {
      event_id: "source-0",
      origin: "model",
      source_index: 0,
      written_pitch_midi: "70",
      onset_seconds: "0.1",
      offset_seconds: "0.6",
      velocity: "90",
      confidence: 0.42,
      is_low_confidence: true,
    },
  ];

  it("derives concert pitch immediately for each saxophone", () => {
    expect(validateDraftEvents(valid, "soprano").events[0]?.pitch_concert_midi).toBe(68);
    expect(validateDraftEvents(valid, "alto").events[0]?.pitch_concert_midi).toBe(61);
    expect(validateDraftEvents(valid, "tenor").events[0]?.pitch_concert_midi).toBe(56);
    expect(validateDraftEvents(valid, "baritone").events[0]?.pitch_concert_midi).toBe(49);
  });

  it.each([
    ["written_pitch_midi", "", "Written MIDI is required."],
    ["written_pitch_midi", "1.5", "Written MIDI must be an integer from 0 to 127."],
    ["written_pitch_midi", "200", "Written MIDI must be an integer from 0 to 127."],
    ["onset_seconds", "-1", "Onset must be a finite non-negative number."],
    ["onset_seconds", "", "Onset is required."],
    ["offset_seconds", "0.1", "Offset must be greater than onset."],
    ["velocity", "128", "Velocity must be an integer from 0 to 127."],
  ])("reports inline %s validation", (field, value, message) => {
    const draft = [{ ...valid[0], [field]: value }] as DraftRevisionEvent[];
    const result = validateDraftEvents(draft, "alto");
    expect(result.errors[`source-0.${field}`]).toBe(message);
    expect(result.isValid).toBe(false);
  });

  it("rejects derived concert pitch and duplicate event IDs", () => {
    const invalid = [{ ...valid[0], written_pitch_midi: "8" }, { ...valid[0] }];
    const result = validateDraftEvents(invalid, "baritone");
    expect(result.errors["source-0.written_pitch_midi"]).toContain("Concert MIDI");
    expect(result.errors["source-0.event_id"]).toBe("Event ID must be unique.");
    expect(result.isValid).toBe(false);
  });
});
