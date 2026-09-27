import { render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TranscriptionReviewView } from "./transcription-review";
import { TranscriptionApiError, type TranscriptionReview } from "@/lib/transcription-api";

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

function renderReview(load = vi.fn().mockResolvedValue(REVIEW)) {
  render(<TranscriptionReviewView jobId={JOB_ID} load={load} />);
  return load;
}

describe("TranscriptionReviewView", () => {
  it("renders loading then complete semantic table and timeline", async () => {
    const load = renderReview();
    expect(screen.getByText("Loading transcription notes…")).toHaveAttribute("aria-live", "polite");

    expect(await screen.findByRole("heading", { name: "Transcription notes" })).toBeVisible();
    expect(load).toHaveBeenCalledTimes(1);
    expect(screen.getByText("2 note events · 1 low confidence")).toBeVisible();
    expect(
      screen.getByText("Confidence is a model signal, not calibrated accuracy."),
    ).toBeVisible();

    const table = screen.getByRole("table", { name: "All transcription note events" });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(3);
    expect(within(rows[1]).getByText("69")).toBeVisible();
    expect(within(rows[1]).getByText("60")).toBeVisible();
    expect(within(rows[1]).getAllByText("0.5 s")).toHaveLength(2);
    expect(within(rows[1]).getByText("Low confidence")).toBeVisible();
    expect(within(rows[2]).getByText("Regular confidence")).toBeVisible();

    const timeline = screen.getByRole("list", { name: "Note event timeline" });
    const items = within(timeline).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveAttribute("data-onset-seconds", "0");
    expect(items[0]).toHaveAttribute("data-offset-seconds", "0.5");
    expect(items[0]).toHaveAttribute("aria-describedby", "confidence-explanation");
    expect(items[0]).toHaveTextContent("Low confidence");
    expect(items[0].className).toContain("low-confidence");
  });

  it("supports overlapping events without reordering or dropping them", async () => {
    renderReview();
    const timeline = await screen.findByRole("list", { name: "Note event timeline" });
    const items = within(timeline).getAllByRole("listitem");
    expect(items.map((item) => item.getAttribute("data-event-index"))).toEqual(["0", "1"]);
  });

  it("distinguishes an empty successful result from not ready", async () => {
    renderReview(
      vi.fn().mockResolvedValue({
        ...REVIEW,
        summary: { event_count: 0, low_confidence_count: 0 },
        events: [],
      }),
    );
    expect(await screen.findByText("No note events were produced.")).toBeVisible();
    expect(
      screen.queryByText("Transcription notes are not available yet."),
    ).not.toBeInTheDocument();
  });

  it.each([
    [409, "TRANSCRIPTION_RESULT_NOT_READY", "Transcription notes are not available yet."],
    [404, "TRANSCRIPTION_NOT_FOUND", "Transcription job not found."],
    [502, "AI_SERVICE_ERROR", "The transcription service returned an invalid response."],
  ])("renders functional error state for %s", async (status, code, message) => {
    renderReview(
      vi.fn().mockRejectedValue(new TranscriptionApiError(code, message, "job_id", status)),
    );
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(message);
    await waitFor(() => expect(alert).toHaveFocus());
    expect(screen.getByRole("link", { name: "Back to job progress" })).toHaveAttribute(
      "href",
      `/transcriptions/${JOB_ID}`,
    );
  });

  it("does not expose editing playback or polling controls", async () => {
    renderReview();
    await screen.findByRole("table");
    expect(
      screen.queryByRole("button", { name: /edit|delete|play|pause|refresh/i }),
    ).not.toBeInTheDocument();
  });
});
