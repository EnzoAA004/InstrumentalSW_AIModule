import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { TranscriptionJob } from "@/lib/transcription-api";
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
  filename: "take.wav",
  size_bytes: 3,
  audio_sha256: SHA,
  saxophone_type: "alto",
  input_mode: "solo",
};
const HISTORY: TranscriptionRevisionHistory = {
  job_id: JOB_ID,
  latest_revision_number: 0,
  revision_count: 1,
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
  ],
};
const REVISION: TranscriptionRevision = {
  job_id: JOB_ID,
  revision_number: 0,
  parent_revision_number: null,
  created_at: "2026-07-22T12:00:00Z",
  saxophone_type: "alto",
  schema_version: "1.0",
  derived_artifacts_status: "CURRENT",
  summary: { event_count: 2, model_event_count: 2, human_event_count: 0 },
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
      confidence: 0.4,
      is_low_confidence: true,
    },
    {
      event_id: "source-1",
      origin: "model",
      source_index: 1,
      pitch_concert_midi: 64,
      written_pitch_midi: 73,
      onset_seconds: 0.5,
      offset_seconds: 1.5,
      velocity: 80,
      confidence: 0.8,
      is_low_confidence: false,
    },
  ],
};

function audioFile(name: string): File {
  return new File([new TextEncoder().encode("abc")], name, { type: "audio/wav" });
}

function renderLifecycle(
  overrides: Partial<React.ComponentProps<typeof TranscriptionSynchronizedPlayback>> = {},
) {
  const verifyFile = vi.fn().mockResolvedValue({ sizeBytes: 3, sha256: SHA });
  const createObjectUrl = vi.fn((file: File) => `blob:${file.name}`);
  const revokeObjectUrl = vi.fn();
  const callbacks = new Map<number, FrameRequestCallback>();
  let nextFrame = 1;
  const requestFrame = vi.fn((callback: FrameRequestCallback) => {
    const id = nextFrame;
    nextFrame += 1;
    callbacks.set(id, callback);
    return id;
  });
  const cancelFrame = vi.fn((id: number) => callbacks.delete(id));
  const result = render(
    <TranscriptionSynchronizedPlayback
      jobId={JOB_ID}
      loadJob={vi.fn().mockResolvedValue(JOB)}
      loadHistory={vi.fn().mockResolvedValue(HISTORY)}
      loadRevision={vi.fn().mockResolvedValue(REVISION)}
      verifyFile={verifyFile}
      createObjectUrl={createObjectUrl}
      revokeObjectUrl={revokeObjectUrl}
      requestFrame={requestFrame}
      cancelFrame={cancelFrame}
      {...overrides}
    />,
  );
  return {
    ...result,
    verifyFile,
    createObjectUrl,
    revokeObjectUrl,
    requestFrame,
    cancelFrame,
    callbacks,
  };
}

async function select(name: string): Promise<HTMLAudioElement> {
  const input = await screen.findByLabelText("Select original audio");
  await userEvent.setup().upload(input, audioFile(name));
  return (await screen.findByTestId("verified-local-audio")) as HTMLAudioElement;
}

describe("local object URL lifecycle", () => {
  it("creates one URL only after verification, revokes on replacement and unmount", async () => {
    const lifecycle = renderLifecycle();
    await screen.findByText("Revision 0");
    expect(lifecycle.createObjectUrl).not.toHaveBeenCalled();

    await select("first.wav");
    expect(lifecycle.createObjectUrl).toHaveBeenCalledTimes(1);
    expect(lifecycle.revokeObjectUrl).not.toHaveBeenCalled();

    await userEvent
      .setup()
      .upload(screen.getByLabelText("Select original audio"), audioFile("second.wav"));
    expect(lifecycle.revokeObjectUrl).toHaveBeenCalledWith("blob:first.wav");
    expect(lifecycle.createObjectUrl).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("verified-local-audio")).toHaveAttribute("src", "blob:second.wav");

    lifecycle.unmount();
    expect(lifecycle.revokeObjectUrl).toHaveBeenLastCalledWith("blob:second.wav");
  });

  it("does not create or retain a URL for mismatch", async () => {
    const verifyFile = vi
      .fn()
      .mockRejectedValue(Object.assign(new Error("mismatch"), { code: "AUDIO_HASH_MISMATCH" }));
    const lifecycle = renderLifecycle({ verifyFile });
    await userEvent
      .setup()
      .upload(await screen.findByLabelText("Select original audio"), audioFile("bad.wav"));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This file does not match the transcription job.",
    );
    expect(lifecycle.createObjectUrl).not.toHaveBeenCalled();
    expect(screen.queryByTestId("verified-local-audio")).not.toBeInTheDocument();
  });

  it("aborts and ignores an obsolete verification when selection is replaced", async () => {
    let resolveFirst!: (value: { sizeBytes: number; sha256: string }) => void;
    let resolveSecond!: (value: { sizeBytes: number; sha256: string }) => void;
    const verifyFile = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirst = resolve;
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveSecond = resolve;
          }),
      );
    const lifecycle = renderLifecycle({ verifyFile });
    const input = await screen.findByLabelText("Select original audio");
    const user = userEvent.setup();
    await user.upload(input, audioFile("first.wav"));
    const firstSignal = verifyFile.mock.calls[0]?.[0].signal as AbortSignal;
    await user.upload(input, audioFile("second.wav"));
    expect(firstSignal.aborted).toBe(true);

    resolveSecond({ sizeBytes: 3, sha256: SHA });
    expect(await screen.findByTestId("verified-local-audio")).toHaveAttribute(
      "src",
      "blob:second.wav",
    );
    resolveFirst({ sizeBytes: 3, sha256: SHA });
    await act(async () => Promise.resolve());

    expect(lifecycle.createObjectUrl).toHaveBeenCalledTimes(1);
    expect(lifecycle.createObjectUrl).toHaveBeenCalledWith(
      expect.objectContaining({ name: "second.wav" }),
    );
    expect(screen.getByTestId("verified-local-audio")).toHaveAttribute("src", "blob:second.wav");
  });

  it("revokes the URL after a media error when playback can no longer use it", async () => {
    const lifecycle = renderLifecycle();
    const audio = await select("decode.wav");
    fireEvent.error(audio);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The browser could not decode this audio file.",
    );
    expect(lifecycle.revokeObjectUrl).toHaveBeenCalledWith("blob:decode.wav");
    expect(screen.queryByTestId("verified-local-audio")).not.toBeInTheDocument();
  });
});

describe("media and animation frame lifecycle", () => {
  it("runs at most one requestAnimationFrame loop and cancels it on pause, ended and unmount", async () => {
    const lifecycle = renderLifecycle();
    const audio = await select("take.wav");
    Object.defineProperty(audio, "currentTime", { configurable: true, writable: true, value: 0 });
    Object.defineProperty(audio, "duration", { configurable: true, value: 2 });
    fireEvent.loadedMetadata(audio);

    fireEvent.play(audio);
    fireEvent.play(audio);
    expect(lifecycle.requestFrame).toHaveBeenCalledTimes(1);
    const firstId = [...lifecycle.callbacks.keys()][0];
    audio.currentTime = 0.75;
    act(() => lifecycle.callbacks.get(firstId)?.(16));
    expect(screen.getByText("Current time: 0:00.750")).toBeVisible();
    expect(screen.getByRole("listitem", { name: /source-0/i })).toHaveTextContent("Active now");
    expect(screen.getByRole("listitem", { name: /source-1/i })).toHaveTextContent("Active now");
    expect(lifecycle.requestFrame).toHaveBeenCalledTimes(2);

    fireEvent.pause(audio);
    expect(screen.getByText("Playback paused.")).toBeVisible();
    expect(lifecycle.cancelFrame).toHaveBeenCalled();

    fireEvent.play(audio);
    expect(lifecycle.requestFrame).toHaveBeenCalledTimes(3);
    fireEvent.ended(audio);
    expect(screen.getByText("Playback ended.")).toBeVisible();
    expect(lifecycle.cancelFrame).toHaveBeenCalledTimes(2);

    fireEvent.play(audio);
    lifecycle.unmount();
    expect(lifecycle.cancelFrame).toHaveBeenCalledTimes(3);
  });

  it("corrects current time immediately on timeupdate, seeking and seeked", async () => {
    renderLifecycle();
    const audio = await select("take.wav");
    Object.defineProperty(audio, "currentTime", { configurable: true, writable: true, value: 0.1 });
    fireEvent.timeUpdate(audio);
    expect(screen.getByText("Current time: 0:00.100")).toBeVisible();
    audio.currentTime = 0.5;
    fireEvent.seeking(audio);
    expect(screen.getByText("Current time: 0:00.500")).toBeVisible();
    audio.currentTime = 1.5;
    fireEvent.seeked(audio);
    expect(screen.getByText("Current time: 0:01.500")).toBeVisible();
  });
});
