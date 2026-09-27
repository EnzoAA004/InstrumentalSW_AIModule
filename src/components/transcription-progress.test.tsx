import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TranscriptionProgress } from "./transcription-progress";
import { TranscriptionApiError, type TranscriptionJob } from "@/lib/transcription-api";

const JOB_ID = "11111111-1111-1111-1111-111111111111";
const UPLOADED: TranscriptionJob = {
  job_id: JOB_ID,
  status: "UPLOADED",
  filename: "take.wav",
  size_bytes: 15,
  audio_sha256: "a".repeat(64),
  saxophone_type: "alto",
  input_mode: "solo",
};

function renderProgress(load = vi.fn().mockResolvedValue(UPLOADED)) {
  const user = userEvent.setup();
  render(<TranscriptionProgress jobId={JOB_ID} load={load} pollIntervalMs={60_000} />);
  return { user, load };
}

describe("TranscriptionProgress", () => {
  it("loads immediately and displays every job field with accessible status text", async () => {
    renderProgress();

    expect(screen.getByRole("heading", { name: "Job progress" })).toBeVisible();
    expect(screen.getByText("Loading current job status…")).toHaveAttribute("aria-live", "polite");

    expect(await screen.findByText("Current status: UPLOADED")).toBeVisible();
    expect(screen.getByText(JOB_ID)).toBeVisible();
    expect(screen.getByText("take.wav")).toBeVisible();
    expect(screen.getByText("alto")).toBeVisible();
    expect(screen.getByText("solo")).toBeVisible();
    expect(screen.getByText("15 bytes")).toBeVisible();
    expect(screen.getByText("a".repeat(64))).toHaveClass("technical-value");
    expect(screen.getByText("Automatic updates are active.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Refresh now" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Pause automatic updates" })).toBeEnabled();
    expect(screen.getByRole("link", { name: "Back to upload" })).toHaveAttribute("href", "/");
  });

  it("shows FAILED as terminal and does not present resume as active progress", async () => {
    renderProgress(vi.fn().mockResolvedValue({ ...UPLOADED, status: "FAILED" }));

    expect(await screen.findByText("Current status: FAILED")).toBeVisible();
    expect(screen.getByText("This job is in a terminal failed state.")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Pause automatic updates" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh now" })).toBeEnabled();
  });

  it("shows an unknown status safely, pauses polling, and allows manual refresh", async () => {
    renderProgress(vi.fn().mockResolvedValue({ ...UPLOADED, status: "MYSTERY" }));

    expect(await screen.findByText("Current status: MYSTERY")).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "This status is outside the known UPLOADED and FAILED contract.",
    );
    expect(screen.getByText("Automatic updates are paused.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Refresh now" })).toBeEnabled();
  });

  it.each([
    [404, "TRANSCRIPTION_NOT_FOUND", "Transcription job not found."],
    [502, "AI_SERVICE_ERROR", "The transcription service returned an invalid response."],
    [null, "BACKEND_UNAVAILABLE", "The Saxo service is currently unavailable. Try again."],
  ])("shows a safe error for status %s and supports Try again", async (status, code, message) => {
    const load = vi
      .fn()
      .mockRejectedValueOnce(new TranscriptionApiError(code, message, "job_id", status))
      .mockResolvedValueOnce(UPLOADED);
    const { user } = renderProgress(load);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(message);
    expect(alert).toHaveTextContent(code);
    expect(alert).toHaveFocus();
    expect(screen.getByText("Automatic updates are paused.")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Current status: UPLOADED")).toBeVisible();
    expect(load).toHaveBeenCalledTimes(2);
  });

  it("keeps the last successful job visible after a transient refresh failure", async () => {
    const load = vi
      .fn()
      .mockResolvedValueOnce(UPLOADED)
      .mockRejectedValueOnce(
        new TranscriptionApiError(
          "AI_SERVICE_UNAVAILABLE",
          "The transcription service is unavailable.",
          null,
          502,
        ),
      );
    const { user } = renderProgress(load);
    await screen.findByText("Current status: UPLOADED");

    await user.click(screen.getByRole("button", { name: "Refresh now" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The transcription service is unavailable.",
    );
    expect(screen.getByText("Current status: UPLOADED")).toBeVisible();
    expect(screen.getByText("take.wav")).toBeVisible();
    expect(screen.getByText("Automatic updates are paused.")).toBeVisible();
  });

  it("does not start a second manual request while one is pending", async () => {
    let resolve!: (job: TranscriptionJob) => void;
    const load = vi.fn().mockReturnValue(new Promise<TranscriptionJob>((done) => (resolve = done)));
    const { user } = renderProgress(load);

    await user.click(screen.getByRole("button", { name: "Refresh now" }));
    expect(load).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Refresh now" })).toBeDisabled();

    resolve(UPLOADED);
    await waitFor(() => expect(screen.getByText("Current status: UPLOADED")).toBeVisible());
  });
});
