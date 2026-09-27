"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  getTranscription,
  TranscriptionApiError,
  type GetTranscription,
  type TranscriptionJob,
} from "@/lib/transcription-api";

export type ProgressViewState =
  "loading" | "active" | "paused" | "terminal" | "error" | "unknown_status";

interface ProgressError {
  code: string | null;
  message: string;
}

interface TranscriptionProgressProps {
  jobId: string;
  load?: GetTranscription;
  pollIntervalMs?: number;
}

export function TranscriptionProgress({
  jobId,
  load = getTranscription,
  pollIntervalMs = 3000,
}: TranscriptionProgressProps) {
  const [viewState, setViewState] = useState<ProgressViewState>("loading");
  const [job, setJob] = useState<TranscriptionJob | null>(null);
  const [error, setError] = useState<ProgressError | null>(null);
  const [automaticUpdates, setAutomaticUpdates] = useState(true);
  const [requestPending, setRequestPending] = useState(false);
  const alertRef = useRef<HTMLDivElement>(null);
  const mountedRef = useRef(false);
  const automaticRef = useRef(true);
  const inFlightRef = useRef(false);
  const requestSequenceRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const runRequestRef = useRef<() => void>(() => undefined);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const runRequest = useCallback(async () => {
    if (!mountedRef.current || inFlightRef.current) return;
    clearTimer();
    const sequence = ++requestSequenceRef.current;
    const controller = new AbortController();
    controllerRef.current = controller;
    inFlightRef.current = true;
    setRequestPending(true);
    setError(null);

    try {
      const current = await load(jobId, controller.signal);
      if (!mountedRef.current || sequence !== requestSequenceRef.current) return;
      setJob(current);
      if (current.status === "FAILED") {
        automaticRef.current = false;
        setAutomaticUpdates(false);
        setViewState("terminal");
        return;
      }
      if (current.status !== "UPLOADED") {
        automaticRef.current = false;
        setAutomaticUpdates(false);
        setViewState("unknown_status");
        return;
      }
      setViewState(automaticRef.current ? "active" : "paused");
      if (automaticRef.current) {
        timerRef.current = setTimeout(() => {
          timerRef.current = null;
          runRequestRef.current();
        }, pollIntervalMs);
      }
    } catch (caught) {
      if (
        controller.signal.aborted ||
        !mountedRef.current ||
        sequence !== requestSequenceRef.current
      ) {
        return;
      }
      automaticRef.current = false;
      setAutomaticUpdates(false);
      setViewState("error");
      setError(
        caught instanceof TranscriptionApiError
          ? { code: caught.code, message: caught.message }
          : { code: null, message: "An unexpected error prevented the status update. Try again." },
      );
    } finally {
      if (sequence === requestSequenceRef.current) {
        inFlightRef.current = false;
        controllerRef.current = null;
        if (mountedRef.current) setRequestPending(false);
      }
    }
  }, [clearTimer, jobId, load, pollIntervalMs]);

  useEffect(() => {
    runRequestRef.current = () => void runRequest();
  }, [runRequest]);

  useEffect(() => {
    mountedRef.current = true;
    automaticRef.current = true;
    queueMicrotask(() => runRequestRef.current());
    return () => {
      mountedRef.current = false;
      clearTimer();
      requestSequenceRef.current += 1;
      controllerRef.current?.abort();
      controllerRef.current = null;
      inFlightRef.current = false;
    };
  }, [clearTimer]);

  useEffect(() => {
    if (viewState === "error") alertRef.current?.focus();
  }, [viewState, error]);

  function pause() {
    automaticRef.current = false;
    setAutomaticUpdates(false);
    clearTimer();
    requestSequenceRef.current += 1;
    controllerRef.current?.abort();
    controllerRef.current = null;
    inFlightRef.current = false;
    setRequestPending(false);
    setViewState("paused");
  }

  function resume() {
    if (inFlightRef.current) return;
    automaticRef.current = true;
    setAutomaticUpdates(true);
    setViewState(job === null ? "loading" : "active");
    void runRequest();
  }

  function refresh() {
    void runRequest();
  }

  const showPause =
    automaticUpdates && !["terminal", "error", "unknown_status"].includes(viewState);
  const showResume = viewState === "paused";

  return (
    <section className="upload-card progress-card" aria-labelledby="progress-title">
      <div className="intro-block">
        <p className="eyebrow">InstrumentalSW</p>
        <h1 id="progress-title">Job progress</h1>
        <p className="intro-copy">
          This page reports the current state returned by the server. It does not estimate a
          percentage or processing stage.
        </p>
      </div>

      {error !== null ? (
        <div className="error-summary" role="alert" tabIndex={-1} ref={alertRef}>
          <h2>We could not update the job</h2>
          <p>{error.message}</p>
          {error.code !== null ? <p className="technical-line">Code: {error.code}</p> : null}
          <button
            className="secondary-button"
            type="button"
            onClick={refresh}
            disabled={requestPending}
          >
            Try again
          </button>
        </div>
      ) : null}

      {viewState === "unknown_status" && job !== null ? (
        <div className="warning-summary" role="alert">
          This status is outside the known UPLOADED and FAILED contract. Automatic updates have been
          paused.
        </div>
      ) : null}

      {job === null ? (
        <p className="request-status" aria-live="polite">
          Loading current job status…
        </p>
      ) : (
        <JobDetails job={job} />
      )}

      <div className="polling-status" aria-live="polite">
        <span>
          {automaticUpdates ? "Automatic updates are active." : "Automatic updates are paused."}
        </span>
        <span>
          {requestPending
            ? "Checking for updates."
            : error === null
              ? "Last request succeeded."
              : "Waiting for manual retry."}
        </span>
      </div>

      {viewState === "terminal" ? (
        <p className="terminal-message">This job is in a terminal failed state.</p>
      ) : null}

      <div className="progress-actions">
        <button
          className="secondary-button"
          type="button"
          onClick={refresh}
          disabled={requestPending}
        >
          Refresh now
        </button>
        {showPause ? (
          <button className="secondary-button" type="button" onClick={pause}>
            Pause automatic updates
          </button>
        ) : null}
        {showResume ? (
          <button className="secondary-button" type="button" onClick={resume}>
            Resume automatic updates
          </button>
        ) : null}
        <Link className="text-link" href={`/transcriptions/${jobId}/review`}>
          View notes
        </Link>
        <Link className="text-link" href="/">
          Back to upload
        </Link>
      </div>
    </section>
  );
}

function JobDetails({ job }: { job: TranscriptionJob }) {
  return (
    <div>
      <p className="current-status" aria-live="polite">
        Current status: {job.status}
      </p>
      <dl className="job-details">
        <Detail label="Job ID" value={job.job_id} technical />
        <Detail label="Filename" value={job.filename} />
        <Detail label="Saxophone" value={job.saxophone_type} />
        <Detail label="Audio mode" value={job.input_mode} />
        <Detail label="File size" value={formatBytes(job.size_bytes)} />
        <Detail label="Audio SHA-256" value={job.audio_sha256} technical />
      </dl>
    </div>
  );
}

function Detail({
  label,
  value,
  technical = false,
}: {
  label: string;
  value: string;
  technical?: boolean;
}) {
  return (
    <div className="detail-row">
      <dt>{label}</dt>
      <dd className={technical ? "technical-value" : undefined}>{value}</dd>
    </div>
  );
}

function formatBytes(size: number): string {
  return size === 1 ? "1 byte" : `${size.toLocaleString("en-US")} bytes`;
}
