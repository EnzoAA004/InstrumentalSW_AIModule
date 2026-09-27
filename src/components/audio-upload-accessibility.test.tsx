import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AudioUploadForm } from "./audio-upload-form";
import { TranscriptionApiError } from "@/lib/transcription-api";

describe("AudioUploadForm error association", () => {
  it("associates a file error with the complete alert summary", async () => {
    const user = userEvent.setup();
    const submit = vi
      .fn()
      .mockRejectedValue(
        new TranscriptionApiError(
          "UNSUPPORTED_AUDIO_FORMAT",
          "Only MP3 and WAV files are supported.",
          "file",
          415,
        ),
      );
    render(<AudioUploadForm submit={submit} />);
    const input = screen.getByLabelText("Audio file");

    await user.upload(input, new File(["audio"], "take.wav", { type: "audio/wav" }));
    await user.click(screen.getByRole("button", { name: "Create transcription job" }));

    expect(await screen.findByRole("alert")).toHaveAttribute("id", "upload-error");
    expect(input).toHaveAttribute("aria-describedby", "file-help upload-error");
  });
});
