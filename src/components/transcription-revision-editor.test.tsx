import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TranscriptionRevisionEditor } from "./transcription-revision-editor";
import { TranscriptionApiError } from "@/lib/transcription-api";
import type {
  RegenerationRequest,
  TranscriptionRevision,
  TranscriptionRevisionHistory,
} from "@/lib/transcription-revisions";

const JOB_ID = "11111111-1111-1111-1111-111111111111";
const REVISION_ZERO: TranscriptionRevision = {
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
    {
      event_id: "source-1",
      origin: "model",
      source_index: 1,
      pitch_concert_midi: 67,
      written_pitch_midi: 76,
      onset_seconds: 0.25,
      offset_seconds: 1,
      velocity: 100,
      confidence: 0.82,
      is_low_confidence: false,
    },
  ],
  summary: { event_count: 2, model_event_count: 2, human_event_count: 0 },
  derived_artifacts_status: "CURRENT",
  schema_version: "1.0",
};
const REVISION_ONE: TranscriptionRevision = {
  ...REVISION_ZERO,
  revision_number: 1,
  parent_revision_number: 0,
  created_at: "2026-07-22T12:00:00Z",
  events: [
    { ...REVISION_ZERO.events[0], written_pitch_midi: 70, pitch_concert_midi: 61 },
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
};
const HISTORY: TranscriptionRevisionHistory = {
  job_id: JOB_ID,
  latest_revision_number: 0,
  revision_count: 1,
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
  ],
};

function setup(overrides: Partial<Parameters<typeof TranscriptionRevisionEditor>[0]> = {}) {
  const loadHistory = vi.fn().mockResolvedValue(HISTORY);
  const loadRevision = vi.fn().mockResolvedValue(REVISION_ZERO);
  const saveRevision = vi.fn().mockResolvedValue(REVISION_ONE);
  const regenerate = vi.fn().mockResolvedValue({
    request_id: "33333333-3333-3333-3333-333333333333",
    job_id: JOB_ID,
    revision_number: 1,
    status: "REQUESTED",
    requested_artifacts: ["midi", "musicxml", "svg"],
  } satisfies RegenerationRequest);
  render(
    <TranscriptionRevisionEditor
      jobId={JOB_ID}
      loadHistory={loadHistory}
      loadRevision={loadRevision}
      saveRevision={saveRevision}
      requestRegeneration={regenerate}
      {...overrides}
    />,
  );
  return { loadHistory, loadRevision, saveRevision, regenerate };
}

describe("TranscriptionRevisionEditor", () => {
  it("loads history then latest revision without polling", async () => {
    const { loadHistory, loadRevision } = setup();
    expect(screen.getByText("Loading revision editor…")).toHaveAttribute("aria-live", "polite");
    expect(await screen.findByRole("heading", { name: "Edit transcription notes" })).toBeVisible();
    expect(loadHistory).toHaveBeenCalledTimes(1);
    expect(loadRevision).toHaveBeenCalledTimes(1);
    expect(loadRevision).toHaveBeenCalledWith(JOB_ID, 0, expect.any(AbortSignal));
    expect(screen.getByRole("combobox", { name: "Revision history" })).toHaveValue("0");
    expect(screen.getByText("Revision 0 — original")).toBeVisible();
    expect(screen.getAllByText("Model event")).toHaveLength(2);
    expect(screen.getByText("Concert MIDI: 60")).toBeVisible();
  });

  it("validates immediately and disables save until corrected", async () => {
    setup();
    const user = userEvent.setup();
    const written = await screen.findByRole("spinbutton", { name: "Written MIDI for source-0" });
    await user.clear(written);
    await user.type(written, "200");
    expect(screen.getByText("Written MIDI must be an integer from 0 to 127.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Save revision" })).toBeDisabled();

    await user.clear(written);
    await user.type(written, "70");
    expect(screen.getByText("Concert MIDI: 61")).toBeVisible();
    expect(screen.getByRole("button", { name: "Save revision" })).toBeEnabled();
  });

  it("adds human note with no fake confidence deletes with confirmation and discards locally", async () => {
    setup();
    const user = userEvent.setup();
    await screen.findByRole("table", { name: "Editable note events" });
    await user.click(screen.getByRole("button", { name: "Add note" }));
    expect(screen.getByText("Human-added event")).toBeVisible();
    const table = screen.getByRole("table", { name: "Editable note events" });
    expect(within(table).getByText("Not applicable")).toBeVisible();
    expect(within(table).getByText("Human edit")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Delete source-1" }));
    expect(screen.getByRole("button", { name: "Confirm delete source-1" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Confirm delete source-1" }));
    expect(screen.queryByLabelText("Written MIDI for source-1")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Discard local changes" }));
    expect(screen.getByRole("spinbutton", { name: "Written MIDI for source-1" })).toBeVisible();
    expect(screen.queryByText("Human-added event")).not.toBeInTheDocument();
  });

  it("saves one explicit revision operation batch and shows stale artifacts", async () => {
    const { saveRevision } = setup();
    const user = userEvent.setup();
    const written = await screen.findByRole("spinbutton", { name: "Written MIDI for source-0" });
    await user.clear(written);
    await user.type(written, "70");
    await user.click(screen.getByRole("button", { name: "Add note" }));
    await user.click(screen.getByRole("button", { name: "Delete source-1" }));
    await user.click(screen.getByRole("button", { name: "Confirm delete source-1" }));
    await user.click(screen.getByRole("button", { name: "Save revision" }));

    expect(saveRevision).toHaveBeenCalledTimes(1);
    expect(saveRevision).toHaveBeenCalledWith(
      JOB_ID,
      expect.objectContaining({
        base_revision_number: 0,
        operations: expect.arrayContaining([
          expect.objectContaining({ type: "update", event_id: "source-0", written_pitch_midi: 70 }),
          expect.objectContaining({ type: "add", velocity: 64 }),
          { type: "delete", event_id: "source-1" },
        ]),
      }),
      expect.any(AbortSignal),
    );
    expect(await screen.findByText("Derived artifacts are stale.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Request artifact regeneration" })).toBeEnabled();
  });

  it("keeps the local draft after 409 and can reload latest explicitly", async () => {
    const saveRevision = vi
      .fn()
      .mockRejectedValue(
        new TranscriptionApiError(
          "REVISION_CONFLICT",
          "The transcription revision has changed.",
          "base_revision_number",
          409,
        ),
      );
    const latestHistory = { ...HISTORY, latest_revision_number: 1, revision_count: 2 };
    const loadHistory = vi.fn().mockResolvedValueOnce(HISTORY).mockResolvedValueOnce(latestHistory);
    const loadRevision = vi
      .fn()
      .mockResolvedValueOnce(REVISION_ZERO)
      .mockResolvedValueOnce(REVISION_ONE);
    setup({ saveRevision, loadHistory, loadRevision });
    const user = userEvent.setup();
    const written = await screen.findByRole("spinbutton", { name: "Written MIDI for source-0" });
    await user.clear(written);
    await user.type(written, "70");
    await user.click(screen.getByRole("button", { name: "Save revision" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The transcription revision has changed.",
    );
    expect(written).toHaveValue(70);
    expect(screen.getByRole("button", { name: "Reload latest revision" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Reload latest revision" }));
    expect(loadHistory).toHaveBeenCalledTimes(2);
    expect(loadRevision).toHaveBeenLastCalledWith(JOB_ID, 1, expect.any(AbortSignal));
  });

  it("shows historical revisions as read-only and returns to latest", async () => {
    const history = {
      job_id: JOB_ID,
      latest_revision_number: 1,
      revision_count: 2,
      revisions: [
        HISTORY.revisions[0],
        {
          revision_number: 1,
          parent_revision_number: 0,
          created_at: "2026-07-22T12:00:00Z",
          event_count: 2,
          model_event_count: 1,
          human_event_count: 1,
          derived_artifacts_status: "STALE" as const,
        },
      ],
    };
    const loadRevision = vi
      .fn()
      .mockResolvedValueOnce(REVISION_ONE)
      .mockResolvedValueOnce(REVISION_ZERO);
    setup({ loadHistory: vi.fn().mockResolvedValue(history), loadRevision });
    const user = userEvent.setup();
    const selector = await screen.findByRole("combobox", { name: "Revision history" });
    expect(selector).toHaveValue("1");
    await user.selectOptions(selector, "0");
    expect(await screen.findByText("Historical revisions are read-only.")).toBeVisible();
    expect(screen.getByRole("spinbutton", { name: "Written MIDI for source-0" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Add note" })).not.toBeInTheDocument();
  });

  it("records regeneration and honestly reports the missing worker", async () => {
    setup({
      loadHistory: vi.fn().mockResolvedValue({
        ...HISTORY,
        latest_revision_number: 1,
        revision_count: 2,
        revisions: [
          HISTORY.revisions[0],
          {
            revision_number: 1,
            parent_revision_number: 0,
            created_at: REVISION_ONE.created_at,
            event_count: 2,
            model_event_count: 1,
            human_event_count: 1,
            derived_artifacts_status: "STALE",
          },
        ],
      }),
      loadRevision: vi.fn().mockResolvedValue(REVISION_ONE),
    });
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Request artifact regeneration" }));
    expect(await screen.findByText("Regeneration requested.")).toBeVisible();
    expect(screen.getByText("No processing worker is connected yet.")).toBeVisible();
    expect(
      screen.queryByText(/completed|midi regenerated|score regenerated|eta|%/i),
    ).not.toBeInTheDocument();
  });

  it("links back to read-only review and exposes no autosave polling or playback", async () => {
    setup();
    await screen.findByRole("table");
    expect(screen.getByRole("link", { name: "Back to read-only review" })).toHaveAttribute(
      "href",
      `/transcriptions/${JOB_ID}/review`,
    );
    expect(screen.queryByText(/autosave|automatic save|polling/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /play|pause|download/i })).not.toBeInTheDocument();
  });
});
