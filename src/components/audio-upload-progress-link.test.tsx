import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AudioUploadForm } from "./audio-upload-form";
import type { TranscriptionJob } from "@/lib/transcription-api";

const JOB: TranscriptionJob = {
  job_id: "11111111-1111-1111-1111-111111111111",
  status: "UPLOADED",
  filename: "take.wav",
  size_bytes: 15,
  audio_sha256: "a".repeat(64),
  saxophone_type: "alto",
  input_mode: "solo",
};

describe("upload success progress navigation", () => {
  it("links to the exact job route and retains the new-upload action", async () => {
    const user = userEvent.setup();
    render(<AudioUploadForm submit={vi.fn().mockResolvedValue(JOB)} />);

    await user.upload(
      screen.getByLabelText("Audio file"),
      new File(["synthetic-audio"], "take.wav", { type: "audio/wav" }),
    );
    await user.click(screen.getByRole("button", { name: "Create transcription job" }));

    expect(await screen.findByRole("link", { name: "View job progress" })).toHaveAttribute(
      "href",
      `/transcriptions/${JOB.job_id}`,
    );
    expect(screen.getByRole("button", { name: "Upload another audio file" })).toBeVisible();
  });
});
