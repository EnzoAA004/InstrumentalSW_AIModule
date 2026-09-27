import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AudioUploadForm } from "./audio-upload-form";
import { TranscriptionApiError, type TranscriptionJob } from "@/lib/transcription-api";

const SUCCESS: TranscriptionJob = {
  job_id: "11111111-1111-1111-1111-111111111111",
  status: "UPLOADED",
  filename: "take.wav",
  size_bytes: 15,
  audio_sha256: "a".repeat(64),
  saxophone_type: "alto",
  input_mode: "solo",
};

function audio(name: string, content = "synthetic-audio") {
  return new File([content], name, {
    type: name.toLowerCase().endsWith(".mp3") ? "audio/mpeg" : "audio/wav",
  });
}

function setup(submit = vi.fn().mockResolvedValue(SUCCESS)) {
  const user = userEvent.setup();
  render(<AudioUploadForm submit={submit} />);
  return { user, submit };
}

async function choose(user: ReturnType<typeof userEvent.setup>, file: File) {
  await user.upload(screen.getByLabelText("Audio file"), file);
}

describe("AudioUploadForm", () => {
  it("renders visible labels and exact instrument and mode values", () => {
    setup();

    expect(screen.getByRole("heading", { name: "Create a transcription job" })).toBeVisible();
    expect(screen.getByLabelText("Audio file")).toHaveAttribute(
      "accept",
      ".mp3,.wav,audio/mpeg,audio/wav",
    );
    const instrument = screen.getByLabelText("Saxophone type");
    expect([...instrument.querySelectorAll("option")].map((option) => option.value)).toEqual([
      "soprano",
      "alto",
      "tenor",
      "baritone",
    ]);
    const mode = screen.getByLabelText("Audio mode");
    expect([...mode.querySelectorAll("option")].map((option) => option.value)).toEqual([
      "solo",
      "mixture",
    ]);
    expect(screen.getByText(/source separation is not implemented yet/i)).toBeVisible();
  });

  it("requires an audio file without contacting the API and focuses the alert", async () => {
    const { user, submit } = setup();

    await user.click(screen.getByRole("button", { name: "Create transcription job" }));

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Select an MP3 or WAV audio file.");
    expect(alert).toHaveFocus();
    expect(submit).not.toHaveBeenCalled();
  });

  it.each(["take.wav", "TAKE.WAV", "take.mp3", "TAKE.MP3"])(
    "accepts %s and shows filename and human-readable size",
    async (filename) => {
      const { user } = setup();
      await choose(user, audio(filename));

      expect(screen.getByText(filename)).toBeVisible();
      expect(screen.getByText("15 bytes")).toBeVisible();
      expect(screen.getByRole("button", { name: "Create transcription job" })).toBeEnabled();
    },
  );

  it("rejects unsupported and empty files locally", async () => {
    const { user, submit } = setup();

    await choose(user, audio("score.pdf"));
    expect(screen.getByRole("alert")).toHaveTextContent("Only MP3 and WAV files are supported.");
    expect(submit).not.toHaveBeenCalled();

    await choose(user, new File([], "empty.wav", { type: "audio/wav" }));
    expect(screen.getByRole("alert")).toHaveTextContent("The selected audio file is empty.");
    expect(submit).not.toHaveBeenCalled();
  });

  it("replaces the selected file without uploading automatically", async () => {
    const { user, submit } = setup();

    await choose(user, audio("first.wav", "one"));
    expect(screen.getByText("first.wav")).toBeVisible();
    await choose(user, audio("second.mp3", "two"));

    expect(screen.queryByText("first.wav")).not.toBeInTheDocument();
    expect(screen.getByText("second.mp3")).toBeVisible();
    expect(submit).not.toHaveBeenCalled();
  });

  it("submits once with exact selections, disables the button, and announces progress", async () => {
    let resolve!: (job: TranscriptionJob) => void;
    const submit = vi
      .fn()
      .mockReturnValue(new Promise<TranscriptionJob>((done) => (resolve = done)));
    const { user } = setup(submit);
    const file = audio("take.wav");
    await choose(user, file);
    await user.selectOptions(screen.getByLabelText("Saxophone type"), "tenor");
    await user.selectOptions(screen.getByLabelText("Audio mode"), "mixture");

    const button = screen.getByRole("button", { name: "Create transcription job" });
    await user.dblClick(button);

    expect(submit).toHaveBeenCalledTimes(1);
    expect(submit).toHaveBeenCalledWith({
      file,
      saxophoneType: "tenor",
      inputMode: "mixture",
    });
    expect(button).toBeDisabled();
    expect(screen.getByText("Creating transcription job…")).toHaveAttribute("aria-live", "polite");

    resolve({ ...SUCCESS, saxophone_type: "tenor", input_mode: "mixture" });
    await screen.findByText("Job created");
  });

  it("shows every successful response field and can explicitly start another upload", async () => {
    const { user } = setup();
    await choose(user, audio("take.wav"));
    await user.click(screen.getByRole("button", { name: "Create transcription job" }));

    expect(await screen.findByText("Job created")).toBeVisible();
    expect(screen.getByText(SUCCESS.job_id)).toBeVisible();
    expect(screen.getByText("UPLOADED")).toBeVisible();
    expect(screen.getByText("take.wav")).toBeVisible();
    expect(screen.getByText("15 bytes")).toBeVisible();
    expect(screen.getByText("alto")).toBeVisible();
    expect(screen.getByText("solo")).toBeVisible();
    expect(screen.getByText("a".repeat(64))).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Upload another audio file" }));
    expect(screen.getByRole("button", { name: "Create transcription job" })).toBeVisible();
    expect(screen.queryByText("Job created")).not.toBeInTheDocument();
  });

  it("shows stable public errors, preserves selection, focuses alert, and retries", async () => {
    const submit = vi
      .fn()
      .mockRejectedValueOnce(
        new TranscriptionApiError(
          "AUDIO_SIZE_LIMIT_EXCEEDED",
          "The audio exceeds the accepted size limit.",
          "file",
          413,
        ),
      )
      .mockResolvedValueOnce(SUCCESS);
    const { user } = setup(submit);
    await choose(user, audio("take.wav"));

    await user.click(screen.getByRole("button", { name: "Create transcription job" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveFocus();
    expect(alert).toHaveTextContent("The audio exceeds the accepted size limit.");
    expect(alert).toHaveTextContent("AUDIO_SIZE_LIMIT_EXCEEDED");
    expect(alert).toHaveTextContent("Field: file");
    expect(alert).not.toHaveTextContent("stack");
    expect(screen.getByText("take.wav")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(submit).toHaveBeenCalledTimes(2);
    expect(await screen.findByText("Job created")).toBeVisible();
  });

  it("uses a readable unknown error and preserves keyboard navigation", async () => {
    const { user } = setup(vi.fn().mockRejectedValue(new Error("private stack detail")));
    await user.tab();
    expect(screen.getByLabelText("Audio file")).toHaveFocus();
    await choose(user, audio("take.wav"));
    await user.click(screen.getByRole("button", { name: "Create transcription job" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveFocus());
    expect(screen.getByRole("alert")).toHaveTextContent(
      "An unexpected error prevented the upload. Try again.",
    );
    expect(screen.getByRole("alert")).not.toHaveTextContent("private stack detail");
  });
});
