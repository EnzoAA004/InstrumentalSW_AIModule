import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TranscriptionRevisionEditor } from "./transcription-revision-editor";
import { TranscriptionApiError } from "@/lib/transcription-api";
import type {
  TranscriptionRevision,
  TranscriptionRevisionHistory,
} from "@/lib/transcription-revisions";

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
const HISTORY: TranscriptionRevisionHistory = {
  job_id: JOB_ID,
  latest_revision_number: 0,
  revision_count: 1,
  revisions: [
    {
      revision_number: 0,
      parent_revision_number: null,
      created_at: REVISION.created_at,
      event_count: 1,
      model_event_count: 1,
      human_event_count: 0,
      derived_artifacts_status: "CURRENT",
    },
  ],
};

function renderEditor(overrides: Record<string, unknown> = {}) {
  render(
    <TranscriptionRevisionEditor
      jobId={JOB_ID}
      loadHistory={vi.fn().mockResolvedValue(HISTORY)}
      loadRevision={vi.fn().mockResolvedValue(REVISION)}
      saveRevision={vi
        .fn()
        .mockResolvedValue({ ...REVISION, revision_number: 1, parent_revision_number: 0 })}
      requestRegeneration={vi.fn()}
      {...overrides}
    />,
  );
}

describe("TranscriptionRevisionEditor failure states", () => {
  it.each([
    ["TRANSCRIPTION_RESULT_NOT_READY", "Transcription notes are not available yet."],
    ["TRANSCRIPTION_NOT_FOUND", "Transcription job not found."],
  ])("renders and focuses the %s load error", async (code, message) => {
    renderEditor({
      loadHistory: vi
        .fn()
        .mockRejectedValue(new TranscriptionApiError(code, message, "job_id", 409)),
    });
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(message);
    await waitFor(() => expect(alert).toHaveFocus());
  });

  it("renders an unexpected load error without leaking internals", async () => {
    renderEditor({ loadHistory: vi.fn().mockRejectedValue(new Error("private")) });
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "An unexpected error prevented the revision editor from loading.",
    );
  });

  it("keeps the draft after a non-conflict save error", async () => {
    const saveRevision = vi
      .fn()
      .mockRejectedValue(
        new TranscriptionApiError(
          "INVALID_REVISION_EVENT",
          "The revision event is invalid.",
          "operations",
          422,
        ),
      );
    renderEditor({ saveRevision });
    const user = userEvent.setup();
    const written = await screen.findByRole("spinbutton", { name: "Written MIDI for source-0" });
    await user.clear(written);
    await user.type(written, "70");
    await user.click(screen.getByRole("button", { name: "Save revision" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The revision event is invalid.");
    expect(written).toHaveValue(70);
    expect(
      screen.queryByRole("button", { name: "Reload latest revision" }),
    ).not.toBeInTheDocument();
  });

  it("reports a historical revision load error", async () => {
    const history: TranscriptionRevisionHistory = {
      ...HISTORY,
      latest_revision_number: 1,
      revision_count: 2,
      revisions: [
        HISTORY.revisions[0]!,
        {
          revision_number: 1,
          parent_revision_number: 0,
          created_at: "2026-07-22T12:00:00Z",
          event_count: 1,
          model_event_count: 1,
          human_event_count: 0,
          derived_artifacts_status: "STALE",
        },
      ],
    };
    const loadRevision = vi
      .fn()
      .mockResolvedValueOnce({ ...REVISION, revision_number: 1, parent_revision_number: 0 })
      .mockRejectedValueOnce(
        new TranscriptionApiError(
          "REVISION_NOT_FOUND",
          "Missing revision.",
          "revision_number",
          404,
        ),
      );
    renderEditor({ loadHistory: vi.fn().mockResolvedValue(history), loadRevision });
    const user = userEvent.setup();
    const selector = await screen.findByRole("combobox", { name: "Revision history" });
    await user.selectOptions(selector, "0");
    expect(await screen.findByRole("alert")).toHaveTextContent("Missing revision.");
  });

  it("reports regeneration failure and keeps the stale status", async () => {
    const stale = {
      ...REVISION,
      revision_number: 1,
      parent_revision_number: 0,
      derived_artifacts_status: "STALE" as const,
    };
    const history: TranscriptionRevisionHistory = {
      job_id: JOB_ID,
      latest_revision_number: 1,
      revision_count: 2,
      revisions: [
        HISTORY.revisions[0]!,
        {
          revision_number: 1,
          parent_revision_number: 0,
          created_at: stale.created_at,
          event_count: 1,
          model_event_count: 1,
          human_event_count: 0,
          derived_artifacts_status: "STALE",
        },
      ],
    };
    renderEditor({
      loadHistory: vi.fn().mockResolvedValue(history),
      loadRevision: vi.fn().mockResolvedValue(stale),
      requestRegeneration: vi
        .fn()
        .mockRejectedValue(
          new TranscriptionApiError("AI_SERVICE_ERROR", "Request failed.", null, 502),
        ),
    });
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Request artifact regeneration" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Request failed.");
    expect(screen.getByText("Derived artifacts are stale.")).toBeVisible();
  });
});
