import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}

async function settle() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function resolveJob(resolve: (value: TranscriptionJob) => void, job: TranscriptionJob) {
  await act(async () => {
    resolve(job);
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("TranscriptionProgress polling lifecycle", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("loads immediately, waits 3000 ms after completion, and never overlaps requests", async () => {
    const first = deferred<TranscriptionJob>();
    const second = deferred<TranscriptionJob>();
    const load = vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);

    render(<TranscriptionProgress jobId={JOB_ID} load={load} />);
    await settle();
    expect(load).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(load).toHaveBeenCalledTimes(1);

    await resolveJob(first.resolve, UPLOADED);
    expect(screen.getByText("Current status: UPLOADED")).toBeVisible();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_999);
    });
    expect(load).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(load).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(load).toHaveBeenCalledTimes(2);
    await resolveJob(second.resolve, UPLOADED);
  });

  it("pause cancels the next timer and resume performs an immediate request", async () => {
    const load = vi.fn().mockResolvedValue(UPLOADED);
    render(<TranscriptionProgress jobId={JOB_ID} load={load} />);
    await settle();
    expect(screen.getByText("Current status: UPLOADED")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Pause automatic updates" }));
    expect(screen.getByText("Automatic updates are paused.")).toBeVisible();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(6_000);
    });
    expect(load).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Resume automatic updates" }));
    expect(load).toHaveBeenCalledTimes(2);
    await settle();
    expect(screen.getByText("Automatic updates are active.")).toBeVisible();
  });

  it.each(["FAILED", "MYSTERY"])("does not poll again after status %s", async (status) => {
    const load = vi.fn().mockResolvedValue({ ...UPLOADED, status });
    render(<TranscriptionProgress jobId={JOB_ID} load={load} />);
    await settle();
    expect(screen.getByText(`Current status: ${status}`)).toBeVisible();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(6_000);
    });
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("does not retry automatically after an error", async () => {
    const load = vi
      .fn()
      .mockRejectedValue(
        new TranscriptionApiError(
          "BACKEND_UNAVAILABLE",
          "The Saxo service is currently unavailable. Try again.",
          null,
          null,
        ),
      );
    render(<TranscriptionProgress jobId={JOB_ID} load={load} />);
    await settle();
    expect(screen.getByRole("alert")).toBeVisible();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(9_000);
    });
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("aborts the active request and clears the timer on unmount", async () => {
    const pending = deferred<TranscriptionJob>();
    let signal: AbortSignal | undefined;
    const load = vi.fn((_jobId: string, suppliedSignal?: AbortSignal) => {
      signal = suppliedSignal;
      return pending.promise;
    });
    const view = render(<TranscriptionProgress jobId={JOB_ID} load={load} />);
    await settle();

    expect(signal?.aborted).toBe(false);
    view.unmount();
    expect(signal?.aborted).toBe(true);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(6_000);
    });
    expect(load).toHaveBeenCalledTimes(1);
  });

  it("an obsolete aborted response cannot overwrite a newer result", async () => {
    const first = deferred<TranscriptionJob>();
    const second = deferred<TranscriptionJob>();
    const signals: AbortSignal[] = [];
    const load = vi
      .fn()
      .mockImplementationOnce((_id: string, signal?: AbortSignal) => {
        if (signal) signals.push(signal);
        return first.promise;
      })
      .mockImplementationOnce((_id: string, signal?: AbortSignal) => {
        if (signal) signals.push(signal);
        return second.promise;
      });

    render(<TranscriptionProgress jobId={JOB_ID} load={load} />);
    await settle();
    fireEvent.click(screen.getByRole("button", { name: "Pause automatic updates" }));
    expect(signals[0]?.aborted).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Resume automatic updates" }));
    expect(load).toHaveBeenCalledTimes(2);

    await resolveJob(second.resolve, { ...UPLOADED, filename: "new.wav" });
    expect(screen.getByText("new.wav")).toBeVisible();

    await resolveJob(first.resolve, { ...UPLOADED, filename: "old.wav" });
    expect(screen.queryByText("old.wav")).not.toBeInTheDocument();
    expect(screen.getByText("new.wav")).toBeVisible();
  });
});
