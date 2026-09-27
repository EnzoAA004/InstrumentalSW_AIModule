import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TranscriptionProgress } from "./transcription-progress";

const JOB_ID = "11111111-1111-1111-1111-111111111111";

describe("TranscriptionProgress review navigation", () => {
  it("keeps progress controls and links to the reloadable review route", async () => {
    render(
      <TranscriptionProgress
        jobId={JOB_ID}
        pollIntervalMs={60_000}
        load={vi.fn().mockResolvedValue({
          job_id: JOB_ID,
          status: "UPLOADED",
          filename: "take.wav",
          size_bytes: 15,
          audio_sha256: "a".repeat(64),
          saxophone_type: "alto",
          input_mode: "solo",
        })}
      />,
    );

    await screen.findByText("Current status: UPLOADED");
    expect(screen.getByRole("link", { name: "View notes" })).toHaveAttribute(
      "href",
      `/transcriptions/${JOB_ID}/review`,
    );
    expect(screen.getByRole("button", { name: "Refresh now" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Pause automatic updates" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Back to upload" })).toBeVisible();
  });
});
