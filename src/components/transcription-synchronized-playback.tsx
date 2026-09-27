"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { RevisionArtifactDownloads } from "@/components/revision-artifact-downloads";
import {
  getTranscription,
  TranscriptionApiError,
  type GetTranscription,
  type TranscriptionJob,
} from "@/lib/transcription-api";
import {
  LocalAudioVerificationError,
  verifyLocalAudioFile,
  type VerifiedLocalAudioIdentity,
  type VerifyLocalAudioFileInput,
} from "@/lib/local-audio-verification";
import {
  activePlaybackEventIds,
  eventsBeyondAudioDuration,
  formatPlaybackTime,
  resolveTimelineDuration,
} from "@/lib/playback-synchronization";
import {
  getTranscriptionRevision,
  getTranscriptionRevisionHistory,
  type LoadRevision,
  type LoadRevisionHistory,
  type TranscriptionRevision,
  type TranscriptionRevisionEvent,
  type TranscriptionRevisionHistory,
} from "@/lib/transcription-revisions";

type PlaybackState =
  | "loading"
  | "awaiting_audio"
  | "verifying_audio"
  | "ready"
  | "playing"
  | "paused"
  | "ended"
  | "mismatch"
  | "media_error"
  | "api_error";

type VerifyFile = (input: VerifyLocalAudioFileInput) => Promise<VerifiedLocalAudioIdentity>;

interface TranscriptionSynchronizedPlaybackProps {
  jobId: string;
  loadJob?: GetTranscription;
  loadHistory?: LoadRevisionHistory;
  loadRevision?: LoadRevision;
  verifyFile?: VerifyFile;
  createObjectUrl?: (file: File) => string;
  revokeObjectUrl?: (url: string) => void;
  requestFrame?: (callback: FrameRequestCallback) => number;
  cancelFrame?: (frameId: number) => void;
}

const defaultCreateObjectUrl = (file: File): string => URL.createObjectURL(file);
const defaultRevokeObjectUrl = (url: string): void => URL.revokeObjectURL(url);
const defaultRequestFrame = (callback: FrameRequestCallback): number =>
  window.requestAnimationFrame(callback);
const defaultCancelFrame = (frameId: number): void => window.cancelAnimationFrame(frameId);

export function TranscriptionSynchronizedPlayback({
  jobId,
  loadJob = getTranscription,
  loadHistory = getTranscriptionRevisionHistory,
  loadRevision = getTranscriptionRevision,
  verifyFile = verifyLocalAudioFile,
  createObjectUrl = defaultCreateObjectUrl,
  revokeObjectUrl = defaultRevokeObjectUrl,
  requestFrame = defaultRequestFrame,
  cancelFrame = defaultCancelFrame,
}: TranscriptionSynchronizedPlaybackProps) {
  const [state, setState] = useState<PlaybackState>("loading");
  const [job, setJob] = useState<TranscriptionJob | null>(null);
  const [history, setHistory] = useState<TranscriptionRevisionHistory | null>(null);
  const [revision, setRevision] = useState<TranscriptionRevision | null>(null);
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [mediaDuration, setMediaDuration] = useState(Number.NaN);
  const [message, setMessage] = useState<string | null>(null);
  const [reloading, setReloading] = useState(false);

  const audioRef = useRef<HTMLAudioElement>(null);
  const alertRef = useRef<HTMLDivElement>(null);
  const activeObjectUrlRef = useRef<string | null>(null);
  const verificationControllerRef = useRef<AbortController | null>(null);
  const verificationSequenceRef = useRef(0);
  const frameRef = useRef<number | null>(null);
  const playingRef = useRef(false);
  const showArtifactDownloads =
    loadJob === getTranscription &&
    loadHistory === getTranscriptionRevisionHistory &&
    loadRevision === getTranscriptionRevision;

  const revokeActiveObjectUrl = useCallback(() => {
    if (activeObjectUrlRef.current !== null) {
      revokeObjectUrl(activeObjectUrlRef.current);
      activeObjectUrlRef.current = null;
    }
  }, [revokeObjectUrl]);

  const cancelActiveFrame = useCallback(() => {
    if (frameRef.current !== null) {
      cancelFrame(frameRef.current);
      frameRef.current = null;
    }
  }, [cancelFrame]);

  const synchronizeFromMedia = useCallback(() => {
    const time = audioRef.current?.currentTime;
    if (typeof time === "number" && Number.isFinite(time)) setCurrentTime(Math.max(0, time));
  }, []);

  const startFrameLoop = useCallback(() => {
    playingRef.current = true;
    if (frameRef.current !== null) return;
    const tick: FrameRequestCallback = () => {
      frameRef.current = null;
      synchronizeFromMedia();
      if (playingRef.current) frameRef.current = requestFrame(tick);
    };
    frameRef.current = requestFrame(tick);
  }, [requestFrame, synchronizeFromMedia]);

  const stopFrameLoop = useCallback(() => {
    playingRef.current = false;
    cancelActiveFrame();
  }, [cancelActiveFrame]);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    queueMicrotask(() => {
      void Promise.all([loadJob(jobId, controller.signal), loadHistory(jobId, controller.signal)])
        .then(async ([loadedJob, loadedHistory]) => {
          const latest = await loadRevision(
            jobId,
            loadedHistory.latest_revision_number,
            controller.signal,
          );
          if (!active) return;
          setJob(loadedJob);
          setHistory(loadedHistory);
          setRevision(latest);
          setState("awaiting_audio");
        })
        .catch((error: unknown) => {
          if (!active || controller.signal.aborted) return;
          setMessage(apiErrorMessage(error));
          setState("api_error");
        });
    });
    return () => {
      active = false;
      controller.abort();
    };
  }, [jobId, loadHistory, loadJob, loadRevision]);

  useEffect(() => {
    if (["mismatch", "media_error", "api_error"].includes(state)) alertRef.current?.focus();
  }, [state]);

  useEffect(
    () => () => {
      verificationSequenceRef.current += 1;
      verificationControllerRef.current?.abort();
      stopFrameLoop();
      revokeActiveObjectUrl();
    },
    [revokeActiveObjectUrl, stopFrameLoop],
  );

  const events = useMemo(() => revision?.events ?? [], [revision]);
  const timelineDuration = resolveTimelineDuration(events, mediaDuration);
  const activeEventIds = useMemo(
    () => new Set(activePlaybackEventIds(events, currentTime)),
    [currentTime, events],
  );
  const beyondDuration = eventsBeyondAudioDuration(events, mediaDuration);

  async function selectLocalAudio(file: File): Promise<void> {
    if (job === null) return;
    const sequence = verificationSequenceRef.current + 1;
    verificationSequenceRef.current = sequence;
    verificationControllerRef.current?.abort();
    const controller = new AbortController();
    verificationControllerRef.current = controller;

    stopFrameLoop();
    const currentAudio = audioRef.current;
    if (currentAudio !== null && !currentAudio.paused) currentAudio.pause();
    revokeActiveObjectUrl();
    setObjectUrl(null);
    setCurrentTime(0);
    setMediaDuration(Number.NaN);
    setMessage(null);
    setState("verifying_audio");

    try {
      await verifyFile({
        file,
        expectedSizeBytes: job.size_bytes,
        expectedSha256: job.audio_sha256,
        signal: controller.signal,
      });
      if (controller.signal.aborted || sequence !== verificationSequenceRef.current) return;
      const nextUrl = createObjectUrl(file);
      if (sequence !== verificationSequenceRef.current) {
        revokeObjectUrl(nextUrl);
        return;
      }
      activeObjectUrlRef.current = nextUrl;
      setObjectUrl(nextUrl);
      setState("ready");
    } catch (error) {
      if (controller.signal.aborted || sequence !== verificationSequenceRef.current) return;
      setMessage(localVerificationMessage(error));
      setState("mismatch");
    }
  }

  async function reloadLatestRevision(): Promise<void> {
    setReloading(true);
    setMessage(null);
    const controller = new AbortController();
    try {
      const loadedHistory = await loadHistory(jobId, controller.signal);
      const latest = await loadRevision(
        jobId,
        loadedHistory.latest_revision_number,
        controller.signal,
      );
      setHistory(loadedHistory);
      setRevision(latest);
    } catch (error) {
      setMessage(apiErrorMessage(error));
      setState("api_error");
    } finally {
      setReloading(false);
    }
  }

  function handleLoadedMetadata(): void {
    const duration = audioRef.current?.duration;
    if (typeof duration === "number" && Number.isFinite(duration) && duration > 0) {
      setMediaDuration(duration);
    }
    synchronizeFromMedia();
  }

  function handlePlay(): void {
    setState("playing");
    startFrameLoop();
  }

  function handlePause(): void {
    stopFrameLoop();
    synchronizeFromMedia();
    setState((current) => (current === "ended" || current === "media_error" ? current : "paused"));
  }

  function handleEnded(): void {
    stopFrameLoop();
    synchronizeFromMedia();
    setState("ended");
  }

  function handleMediaError(): void {
    stopFrameLoop();
    revokeActiveObjectUrl();
    setObjectUrl(null);
    setMessage("The browser could not decode this audio file.");
    setState("media_error");
  }

  function seekToEvent(event: TranscriptionRevisionEvent): void {
    if (audioRef.current === null) return;
    audioRef.current.currentTime = event.onset_seconds;
    setCurrentTime(event.onset_seconds);
  }

  return (
    <section
      className="upload-card synchronized-playback-card"
      aria-labelledby="synchronized-playback-title"
      data-playback-state={state}
    >
      <p className="eyebrow">InstrumentalSW</p>
      <h1 id="synchronized-playback-title">Synchronized review playback</h1>
      <p className="technical-value">Job ID: {jobId}</p>

      {state === "loading" ? (
        <p className="request-status" aria-live="polite">
          Loading synchronized playback…
        </p>
      ) : null}

      {state === "mismatch" || state === "media_error" || state === "api_error" ? (
        <div className="error-summary" role="alert" tabIndex={-1} ref={alertRef}>
          <h2>{state === "media_error" ? "Audio unavailable" : "Playback unavailable"}</h2>
          <p>{message}</p>
        </div>
      ) : null}

      {job !== null && revision !== null && history !== null ? (
        <>
          <div className="playback-header-row">
            <p className="review-summary" aria-live="polite">
              Revision {revision.revision_number}
            </p>
            <button
              className="secondary-button"
              type="button"
              disabled={reloading}
              onClick={() => void reloadLatestRevision()}
            >
              {reloading ? "Reloading latest revision…" : "Reload latest revision"}
            </button>
          </div>

          <dl className="job-details compact-details">
            <PlaybackDetail label="Original filename" value={job.filename} technical />
            <PlaybackDetail label="Original size" value={`${job.size_bytes} bytes`} />
            <PlaybackDetail label="Saxophone" value={revision.saxophone_type} />
            <PlaybackDetail label="Revision events" value={String(revision.summary.event_count)} />
          </dl>

          <div className="local-audio-selection">
            <label className="field-label" htmlFor="original-audio-file">
              Select original audio
            </label>
            <input
              id="original-audio-file"
              type="file"
              accept=".mp3,.wav,audio/mpeg,audio/wav"
              onChange={(event) => {
                const selected = event.target.files?.[0];
                if (selected !== undefined) void selectLocalAudio(selected);
              }}
            />
            <p>Select the original MP3 or WAV used for this transcription.</p>
            <div className="playback-privacy">
              <p>The selected file stays in this browser session.</p>
              <p>It is used only through a local object URL.</p>
              <p>It is not uploaded again.</p>
            </div>
          </div>

          <VerificationStatus state={state} />

          {objectUrl !== null ? (
            <div className="native-audio-player">
              <audio
                ref={audioRef}
                data-testid="verified-local-audio"
                controls
                preload="metadata"
                src={objectUrl}
                onLoadedMetadata={handleLoadedMetadata}
                onPlay={handlePlay}
                onPause={handlePause}
                onTimeUpdate={synchronizeFromMedia}
                onSeeking={synchronizeFromMedia}
                onSeeked={synchronizeFromMedia}
                onEnded={handleEnded}
                onError={handleMediaError}
              />
              <p className="playback-state-text">{playbackStateText(state)}</p>
              <p>Current time: {formatPlaybackTime(currentTime)}</p>
              <p>
                Audio duration:{" "}
                {Number.isFinite(mediaDuration) && mediaDuration > 0
                  ? formatPlaybackTime(mediaDuration)
                  : "Waiting for metadata"}
              </p>
            </div>
          ) : null}

          {beyondDuration.length > 0 ? (
            <div className="warning-summary" role="alert" aria-label="Timeline duration warning">
              <p>
                {beyondDuration.join(", ")} extends beyond the decoded audio duration. Event timing
                remains unchanged.
              </p>
            </div>
          ) : null}

          <PlaybackTimeline
            events={events}
            duration={timelineDuration}
            currentTime={currentTime}
            activeEventIds={activeEventIds}
            canSeek={objectUrl !== null}
            onSeek={seekToEvent}
          />

          {showArtifactDownloads ? (
            <RevisionArtifactDownloads jobId={jobId} revisionNumber={revision.revision_number} />
          ) : null}
        </>
      ) : null}

      <nav className="progress-actions" aria-label="Synchronized playback navigation">
        <Link className="text-link" href={`/transcriptions/${jobId}/review`}>
          Back to read-only review
        </Link>
        <Link className="text-link" href={`/transcriptions/${jobId}/review/edit`}>
          Back to revision editor
        </Link>
        <Link className="text-link" href={`/transcriptions/${jobId}`}>
          Back to job progress
        </Link>
      </nav>
    </section>
  );
}

function PlaybackTimeline({
  events,
  duration,
  currentTime,
  activeEventIds,
  canSeek,
  onSeek,
}: {
  events: readonly TranscriptionRevisionEvent[];
  duration: number;
  currentTime: number;
  activeEventIds: ReadonlySet<string>;
  canSeek: boolean;
  onSeek: (event: TranscriptionRevisionEvent) => void;
}) {
  return (
    <div className="playback-timeline-scroll" aria-label="Synchronized timeline from zero seconds">
      <div
        className="playback-timeline"
        style={{
          minWidth: `${Math.max(48, duration * 14)}rem`,
          height: `${events.length * 4.8 + 2}rem`,
        }}
      >
        <span className="timeline-origin" aria-hidden="true">
          0 s
        </span>
        <span
          className="playback-cursor"
          aria-label={`Playback cursor at ${formatPlaybackTime(currentTime)}`}
          style={{ left: `${Math.max(0, (currentTime / duration) * 100)}%` }}
        />
        <ol aria-label="Synchronized revision event timeline">
          {events.map((event, order) => {
            const active = activeEventIds.has(event.event_id);
            return (
              <li
                key={event.event_id}
                aria-label={`${event.event_id}, written MIDI ${event.written_pitch_midi}, concert MIDI ${event.pitch_concert_midi}, onset ${event.onset_seconds}, offset ${event.offset_seconds}`}
                className={`playback-event${active ? " active-playback-event" : ""}`}
                data-event-id={event.event_id}
                data-onset-seconds={event.onset_seconds}
                data-offset-seconds={event.offset_seconds}
                style={{
                  left: `${(event.onset_seconds / duration) * 100}%`,
                  width: `${Math.max(((event.offset_seconds - event.onset_seconds) / duration) * 100, 1)}%`,
                  top: `${order * 4.8 + 1.8}rem`,
                }}
              >
                <strong>Written MIDI {event.written_pitch_midi}</strong>
                <span>Concert MIDI {event.pitch_concert_midi}</span>
                <span>
                  {event.origin === "human"
                    ? "Human event — confidence not applicable"
                    : `Confidence ${event.confidence}`}
                </span>
                <span className="active-event-label">{active ? "Active now" : "Inactive"}</span>
                <button
                  type="button"
                  className="timeline-seek-button"
                  disabled={!canSeek}
                  aria-label={`Seek to note ${event.event_id}`}
                  onClick={() => onSeek(event)}
                >
                  Seek to note
                </button>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}

function VerificationStatus({ state }: { state: PlaybackState }) {
  if (state === "verifying_audio") {
    return (
      <p className="request-status" aria-live="polite">
        Verifying audio content…
      </p>
    );
  }
  if (["ready", "playing", "paused", "ended"].includes(state)) {
    return (
      <p className="success-summary" aria-live="polite">
        Audio verified locally. The file was not uploaded.
      </p>
    );
  }
  return null;
}

function PlaybackDetail({
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

function playbackStateText(state: PlaybackState): string {
  if (state === "playing") return "Playback playing.";
  if (state === "paused") return "Playback paused.";
  if (state === "ended") return "Playback ended.";
  return "Audio ready. Playback has not started.";
}

function localVerificationMessage(error: unknown): string {
  if (error instanceof LocalAudioVerificationError && error.code === "WEB_CRYPTO_UNAVAILABLE") {
    return "This browser cannot verify the original audio file with Web Crypto.";
  }
  return "This file does not match the transcription job.";
}

function apiErrorMessage(error: unknown): string {
  return error instanceof TranscriptionApiError
    ? error.message
    : "An unexpected error prevented synchronized playback from loading.";
}
