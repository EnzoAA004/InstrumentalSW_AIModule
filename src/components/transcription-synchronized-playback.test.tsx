import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TranscriptionApiError, type TranscriptionJob } from "@/lib/transcription-api";
import type {
  TranscriptionRevision,
  TranscriptionRevisionHistory,
} from "@/lib/transcription-revisions";
import { TranscriptionSynchronizedPlayback } from "./transcription-synchronized-playback";

const JOB_ID = "11111111-1111-1111-1111-111111111111";
const SHA = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
const JOB: TranscriptionJob = {
  job_id: JOB_ID,
  status: "UPLOADED",
  filename: "original.wav",
  size_bytes: 3,
  audio_sha256: SHA,
  saxophone_type: "alto",
  input_mode: "solo",
};
const HISTORY: TranscriptionRevisionHistory = {
  job_id: JOB_ID,
  latest_revision_number: 2,
  revision_count: 3,
  revisions: [
    {
      revision_number: 0,
      parent_revision_number: null,
      created_at: "2026-07-22T12:00:00Z",
      event_count: 2,
      model_event_count: 2,
      human_event_count: 0,
      derived_artifacts_status: "CURRENT",
    },
    {
      revision_number: 1,
      parent_revision_number: 0,
      created_at: "2026-07-22T12:01:00Z",
      event_count: 2,
      model_event_count: 1,
      human_event_count: 1,
      derived_artifacts_status: "STALE",
    },
    {
      revision_number: 2,
      parent_revision_number: 1,
      created_at: "2026-07-22T12:02:00Z",
      event_count: 3,
      model_event_count: 2,
      human_event_count: 1,
      derived_artifacts_status: "STALE",
    },
  ],
};
const REVISION: TranscriptionRevision = {
  job_id: JOB_ID,
  revision_number: 2,
  parent_revision_number: 1,
  created_at: "2026-07-22T12:02:00Z",
  saxophone_type: "alto",
  schema_version: "1.0",
  derived_artifacts_status: "STALE",
  summary: { event_count: 3, model_event_count: 2, human_event_count: 1 },
  events: [
    {
      event_id: "source-0",
      origin: "model",
      source_index: 0,
      pitch_concert_midi: 60,
      written_pitch_midi: 69,
      onset_seconds: 0,
      offset_seconds: 1,
      velocity: 90,
      confidence: 0.42,
      is_low_confidence: true,
    },
    {
      event_id: "human-1",
      origin: "human",
      source_index: null,
      pitch_concert_midi: 64,
      written_pitch_midi: 73,
      onset_seconds: 0.5,
      offset_seconds: 1.5,
      velocity: 64,
      confidence: null,
      is_low_confidence: null,
    },
    {
      event_id: "source-2",
      origin: "model",
      source_index: 2,
      pitch_concert_midi: 67,
      written_pitch_midi: 76,
      onset_seconds: 2,
      offset_seconds: 4,
      velocity: 100,
      confidence: 0.82,
      is_low_confidence: false,
    },
  ],
};

function file(name = "reattached.wav"): File {
  return new File([new TextEncoder().encode("abc")], name, { type: "audio/wav" });
}

function renderPlayback(
  overrides: Partial<React.ComponentProps<typeof TranscriptionSynchronizedPlayback>> = {},
) {
  const loadJob = vi.fn().mockResolvedValue(JOB);
  const loadHistory = vi.fn().mockResolvedValue(HISTORY);
  const loadRevision = vi.fn().mockResolvedValue(REVISION);
  const verifyFile = vi.fn().mockResolvedValue({ sizeBytes: 3, sha256: SHA });
  const createObjectUrl = vi.fn().mockReturnValue("blob:verified-audio");
  const revokeObjectUrl = vi.fn();
  const result = render(
    <TranscriptionSynchronizedPlayback
      jobId={JOB_ID}
      loadJob={loadJob}
      loadHistory={loadHistory}
      loadRevision={loadRevision}
      verifyFile={verifyFile}
      createObjectUrl={createObjectUrl}
      revokeObjectUrl={revokeObjectUrl}
      {...overrides}
    />,
  );
  return {
    ...result,
    loadJob,
    loadHistory,
    loadRevision,
    verifyFile,
    createObjectUrl,
    revokeObjectUrl,
  };
}

async function attachAudio(user = userEvent.setup()): Promise<HTMLAudioElement> {
  const input = await screen.findByLabelText("Select original audio");
  await user.upload(input, file());
  return (await screen.findByTestId("verified-local-audio")) as HTMLAudioElement;
}

describe("TranscriptionSynchronizedPlayback", () => {
  it("loads job metadata, history, and the latest revision through injected Backend clients", async () => {
    const { loadJob, loadHistory, loadRevision } = renderPlayback();

    expect(screen.getByText("Loading synchronized playback…")).toHaveAttribute(
      "aria-live",
      "polite",
    );
    expect(
      await screen.findByRole("heading", { name: "Synchronized review playback" }),
    ).toBeVisible();
    expect(await screen.findByText("Revision 2")).toBeVisible();
    expect(
      screen.getByText("Select the original MP3 or WAV used for this transcription."),
    ).toBeVisible();
    expect(screen.queryByTestId("verified-local-audio")).not.toBeInTheDocument();
    expect(loadJob).toHaveBeenCalledWith(JOB_ID, expect.any(AbortSignal));
    expect(loadHistory).toHaveBeenCalledWith(JOB_ID, expect.any(AbortSignal));
    expect(loadRevision).toHaveBeenCalledWith(JOB_ID, 2, expect.any(AbortSignal));
  });

  it("verifies locally before exposing native non-autoplay controls and privacy text", async () => {
    const user = userEvent.setup();
    const { verifyFile, createObjectUrl } = renderPlayback();
    const selected = file("renamed.wav");

    await user.upload(await screen.findByLabelText("Select original audio"), selected);

    expect(
      await screen.findByText("Audio verified locally. The file was not uploaded."),
    ).toBeVisible();
    const audio = screen.getByTestId("verified-local-audio");
    expect(audio).toHaveAttribute("controls");
    expect(audio).toHaveAttribute("preload", "metadata");
    expect(audio).not.toHaveAttribute("autoplay");
    expect(audio).toHaveAttribute("src", "blob:verified-audio");
    expect(verifyFile).toHaveBeenCalledWith(
      expect.objectContaining({
        file: selected,
        expectedSizeBytes: 3,
        expectedSha256: SHA,
        signal: expect.any(AbortSignal),
      }),
    );
    expect(createObjectUrl).toHaveBeenCalledWith(selected);
    expect(screen.getByText("The selected file stays in this browser session.")).toBeVisible();
    expect(screen.getByText("It is used only through a local object URL.")).toBeVisible();
    expect(screen.getByText("It is not uploaded again.")).toBeVisible();
  });

  it("renders model and human confidence honestly in preserved API order", async () => {
    renderPlayback();
    await screen.findByText("Revision 2");
    const timeline = screen.getByRole("list", { name: "Synchronized revision event timeline" });
    const events = within(timeline).getAllByRole("listitem");
    expect(events.map((event) => event.getAttribute("data-event-id"))).toEqual([
      "source-0",
      "human-1",
      "source-2",
    ]);
    expect(events[0]).toHaveTextContent("Confidence 0.42");
    expect(events[1]).toHaveTextContent("Human event — confidence not applicable");
    expect(events[2]).toHaveTextContent("Confidence 0.82");
  });

  it("uses media duration after metadata and warns without truncating out-of-range events", async () => {
    renderPlayback();
    const audio = await attachAudio();
    Object.defineProperty(audio, "duration", { configurable: true, value: 3 });
    fireEvent.loadedMetadata(audio);

    expect(screen.getByText("Audio duration: 0:03.000")).toBeVisible();
    const warning = screen.getByRole("alert", { name: "Timeline duration warning" });
    expect(warning).toHaveTextContent("source-2 extends beyond the decoded audio duration");
    const event = screen.getByRole("listitem", { name: /source-2/i });
    expect(event).toHaveAttribute("data-onset-seconds", "2");
    expect(event).toHaveAttribute("data-offset-seconds", "4");
  });

  it("seeks to an event onset without starting playback", async () => {
    const user = userEvent.setup();
    renderPlayback();
    const audio = await attachAudio(user);
    const play = vi.spyOn(audio, "play").mockResolvedValue();
    Object.defineProperty(audio, "currentTime", { configurable: true, writable: true, value: 0 });

    const button = screen.getByRole("button", { name: "Seek to note source-2" });
    button.focus();
    await user.click(button);

    expect(audio.currentTime).toBe(2);
    expect(screen.getByText("Current time: 0:02.000")).toBeVisible();
    expect(play).not.toHaveBeenCalled();
    expect(button).toHaveFocus();
  });

  it("reloads the latest revision manually while preserving verified local audio", async () => {
    const newerHistory: TranscriptionRevisionHistory = {
      ...HISTORY,
      latest_revision_number: 3,
      revision_count: 4,
      revisions: [
        ...HISTORY.revisions,
        {
          revision_number: 3,
          parent_revision_number: 2,
          created_at: "2026-07-22T12:03:00Z",
          event_count: 1,
          model_event_count: 0,
          human_event_count: 1,
          derived_artifacts_status: "STALE",
        },
      ],
    };
    const newerRevision: TranscriptionRevision = {
      ...REVISION,
      revision_number: 3,
      parent_revision_number: 2,
      events: [REVISION.events[1]],
      summary: { event_count: 1, model_event_count: 0, human_event_count: 1 },
    };
    const loadHistory = vi.fn().mockResolvedValueOnce(HISTORY).mockResolvedValueOnce(newerHistory);
    const loadRevision = vi
      .fn()
      .mockResolvedValueOnce(REVISION)
      .mockResolvedValueOnce(newerRevision);
    const user = userEvent.setup();
    const { verifyFile, createObjectUrl } = renderPlayback({ loadHistory, loadRevision });
    const audio = await attachAudio(user);
    Object.defineProperty(audio, "currentTime", {
      configurable: true,
      writable: true,
      value: 0.75,
    });

    await user.click(screen.getByRole("button", { name: "Reload latest revision" }));

    expect(await screen.findByText("Revision 3")).toBeVisible();
    expect(screen.getByTestId("verified-local-audio")).toHaveAttribute(
      "src",
      "blob:verified-audio",
    );
    expect((screen.getByTestId("verified-local-audio") as HTMLAudioElement).currentTime).toBe(0.75);
    expect(verifyFile).toHaveBeenCalledTimes(1);
    expect(createObjectUrl).toHaveBeenCalledTimes(1);
    expect(loadHistory).toHaveBeenCalledTimes(2);
    expect(loadRevision).toHaveBeenLastCalledWith(JOB_ID, 3, expect.any(AbortSignal));
  });

  it.each([
    ["TRANSCRIPTION_RESULT_NOT_READY", "Transcription notes are not available yet."],
    ["TRANSCRIPTION_NOT_FOUND", "Transcription job not found."],
    ["BACKEND_UNAVAILABLE", "The Saxo service is currently unavailable. Try again."],
  ])("shows focused API error %s without polling", async (code, message) => {
    const loadHistory = vi
      .fn()
      .mockRejectedValue(new TranscriptionApiError(code, message, "job_id", 409));
    const { loadJob, loadRevision } = renderPlayback({ loadHistory });

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(message);
    expect(alert).toHaveFocus();
    vi.useFakeTimers();
    await vi.advanceTimersByTimeAsync(10_000);
    vi.useRealTimers();
    expect(loadJob).toHaveBeenCalledTimes(1);
    expect(loadHistory).toHaveBeenCalledTimes(1);
    expect(loadRevision).not.toHaveBeenCalled();
  });

  it("shows controlled mismatch and media decode errors with focused alerts", async () => {
    const verifyFile = vi
      .fn()
      .mockRejectedValue(Object.assign(new Error("mismatch"), { code: "AUDIO_HASH_MISMATCH" }));
    const user = userEvent.setup();
    const first = renderPlayback({ verifyFile });
    await user.upload(await screen.findByLabelText("Select original audio"), file());
    const mismatch = await screen.findByRole("alert");
    expect(mismatch).toHaveTextContent("This file does not match the transcription job.");
    expect(mismatch).toHaveFocus();
    first.unmount();

    renderPlayback();
    const audio = await attachAudio(userEvent.setup());
    fireEvent.error(audio);
    const mediaError = await screen.findByRole("alert");
    expect(mediaError).toHaveTextContent("The browser could not decode this audio file.");
    expect(mediaError).toHaveFocus();
  });

  it("has one heading, visible label, live verification state, keyboard seek controls and textual active state", async () => {
    let resolveVerification!: (value: { sizeBytes: number; sha256: string }) => void;
    const verifyFile = vi.fn().mockReturnValue(
      new Promise((resolve) => {
        resolveVerification = resolve;
      }),
    );
    const user = userEvent.setup();
    renderPlayback({ verifyFile });
    expect(await screen.findAllByRole("heading", { level: 1 })).toHaveLength(1);
    const input = await screen.findByLabelText("Select original audio");
    input.focus();
    await user.upload(input, file());
    expect(screen.getByText("Verifying audio content…")).toHaveAttribute("aria-live", "polite");
    await act(async () => {
      resolveVerification({ sizeBytes: 3, sha256: SHA });
    });
    const audio = await screen.findByTestId("verified-local-audio");
    Object.defineProperty(audio, "currentTime", {
      configurable: true,
      writable: true,
      value: 0.75,
    });
    fireEvent.timeUpdate(audio);
    expect(screen.getByRole("listitem", { name: /source-0/i })).toHaveTextContent("Active now");
    expect(screen.getByRole("listitem", { name: /human-1/i })).toHaveTextContent("Active now");
    expect(screen.getByRole("button", { name: "Seek to note source-0" })).toBeEnabled();
    expect(screen.getByLabelText(/Playback cursor at/)).toBeInTheDocument();
  });
});
