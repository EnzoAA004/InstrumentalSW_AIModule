import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TranscriptionReviewView } from "./transcription-review";
import type { TranscriptionReview } from "@/lib/transcription-api";

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
  summary: { event_count: 0, low_confidence_count: 0 },
  events: [],
};

describe("Transcription review editor navigation", () => {
  it("keeps the read-only view and links explicitly to the editor", async () => {
    render(<TranscriptionReviewView jobId={JOB_ID} load={vi.fn().mockResolvedValue(REVIEW)} />);
    expect(await screen.findByText("No note events were produced.")).toBeVisible();
    expect(screen.getByRole("link", { name: "Edit notes" })).toHaveAttribute(
      "href",
      `/transcriptions/${JOB_ID}/review/edit`,
    );
    expect(screen.getByRole("heading", { name: "Transcription notes" })).toBeVisible();
  });
});
