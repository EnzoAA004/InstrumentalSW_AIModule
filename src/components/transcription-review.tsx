"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { LatestRevisionArtifactDownloads } from "@/components/latest-revision-artifact-downloads";
import {
  getTranscriptionReview,
  TranscriptionApiError,
  type LoadTranscriptionReview,
  type TranscriptionReview,
  type TranscriptionReviewEvent,
} from "@/lib/transcription-api";

type ReviewViewState = "loading" | "ready" | "empty" | "not_ready" | "not_found" | "error";

interface TranscriptionReviewViewProps {
  jobId: string;
  load?: LoadTranscriptionReview;
}

export function TranscriptionReviewView({
  jobId,
  load = getTranscriptionReview,
}: TranscriptionReviewViewProps) {
  const [state, setState] = useState<ReviewViewState>("loading");
  const [review, setReview] = useState<TranscriptionReview | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const alertRef = useRef<HTMLDivElement>(null);
  const showArtifactDownloads = load === getTranscriptionReview;

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    queueMicrotask(() => {
      void load(jobId, controller.signal)
        .then((result) => {
          if (!active) return;
          setReview(result);
          setState(result.events.length === 0 ? "empty" : "ready");
        })
        .catch((error: unknown) => {
          if (!active || controller.signal.aborted) return;
          if (error instanceof TranscriptionApiError) {
            if (error.code === "TRANSCRIPTION_RESULT_NOT_READY") {
              setState("not_ready");
            } else if (error.code === "TRANSCRIPTION_NOT_FOUND") {
              setState("not_found");
            } else {
              setState("error");
            }
            setMessage(error.message);
          } else {
            setState("error");
            setMessage("An unexpected error prevented the note review from loading.");
          }
        });
    });
    return () => {
      active = false;
      controller.abort();
    };
  }, [jobId, load]);

  useEffect(() => {
    if (["not_ready", "not_found", "error"].includes(state)) {
      alertRef.current?.focus();
    }
  }, [state]);

  return (
    <section className="upload-card review-card" aria-labelledby="review-title">
      <p className="eyebrow">InstrumentalSW</p>
      <h1 id="review-title">Transcription notes</h1>
      <p className="intro-copy technical-value">Job ID: {jobId}</p>

      {state === "loading" ? (
        <p className="request-status" aria-live="polite">
          Loading transcription notes…
        </p>
      ) : null}

      {state === "not_ready" || state === "not_found" || state === "error" ? (
        <div className="error-summary" role="alert" tabIndex={-1} ref={alertRef}>
          <h2>Notes unavailable</h2>
          <p>{message}</p>
        </div>
      ) : null}

      {review !== null ? (
        <>
          <ReviewContent review={review} empty={state === "empty"} />
          {showArtifactDownloads ? <LatestRevisionArtifactDownloads jobId={jobId} /> : null}
        </>
      ) : null}

      <nav className="progress-actions" aria-label="Review navigation">
        {review !== null ? (
          <>
            <Link className="text-link" href={`/transcriptions/${jobId}/review/playback`}>
              Play synchronized review
            </Link>
            <Link className="text-link" href={`/transcriptions/${jobId}/review/edit`}>
              Edit notes
            </Link>
          </>
        ) : null}
        <Link className="text-link" href={`/transcriptions/${jobId}`}>
          Back to job progress
        </Link>
        <Link className="text-link" href="/">
          Back to upload
        </Link>
      </nav>
    </section>
  );
}

function ReviewContent({ review, empty }: { review: TranscriptionReview; empty: boolean }) {
  const duration = review.events.reduce(
    (maximum, event) => Math.max(maximum, event.offset_seconds),
    0,
  );
  return (
    <div>
      <p className="review-summary" aria-live="polite">
        {review.summary.event_count} note events · {review.summary.low_confidence_count} low
        confidence
      </p>
      <p id="confidence-explanation">Confidence is a model signal, not calibrated accuracy.</p>
      <dl className="job-details compact-details">
        <Detail label="Saxophone" value={review.saxophone_type} />
        <Detail
          label="Low-confidence threshold"
          value={formatNumber(review.low_confidence_threshold)}
        />
        <Detail label="Confidence method" value={review.confidence_method} technical />
      </dl>

      {empty ? (
        <p className="empty-review">No note events were produced.</p>
      ) : (
        <>
          <Timeline events={review.events} duration={duration} />
          <EventTable events={review.events} />
        </>
      )}
    </div>
  );
}

function Timeline({ events, duration }: { events: TranscriptionReviewEvent[]; duration: number }) {
  return (
    <div className="timeline-scroll" aria-label="Timeline from zero seconds">
      <ol
        className="note-timeline"
        aria-label="Note event timeline"
        style={{
          minWidth: `${Math.max(48, duration * 14)}rem`,
          height: `${events.length * 3.4 + 1}rem`,
        }}
      >
        <li className="timeline-origin" aria-hidden="true">
          0 s
        </li>
        {events.map((event, order) => {
          const left = duration === 0 ? 0 : (event.onset_seconds / duration) * 100;
          const width =
            duration === 0 ? 0 : ((event.offset_seconds - event.onset_seconds) / duration) * 100;
          return (
            <li
              key={event.index}
              className={`timeline-event${event.is_low_confidence ? " low-confidence" : ""}`}
              data-event-index={event.index}
              data-onset-seconds={event.onset_seconds}
              data-offset-seconds={event.offset_seconds}
              aria-describedby="confidence-explanation"
              style={{
                left: `${left}%`,
                width: `${Math.max(width, 1)}%`,
                top: `${order * 3.4 + 1.2}rem`,
              }}
            >
              <strong>Written MIDI {event.written_pitch_midi}</strong>
              <span>Concert MIDI {event.pitch_concert_midi}</span>
              <span>{event.is_low_confidence ? "Low confidence" : "Regular confidence"}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function EventTable({ events }: { events: TranscriptionReviewEvent[] }) {
  return (
    <div className="review-table-scroll">
      <table aria-label="All transcription note events">
        <thead>
          <tr>
            <th>Index</th>
            <th>Written MIDI</th>
            <th>Concert MIDI</th>
            <th>Onset</th>
            <th>Offset</th>
            <th>Duration</th>
            <th>Velocity</th>
            <th>Confidence</th>
            <th>Confidence status</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr
              key={event.index}
              className={event.is_low_confidence ? "low-confidence-row" : undefined}
            >
              <td>{event.index}</td>
              <td>{event.written_pitch_midi}</td>
              <td>{event.pitch_concert_midi}</td>
              <td>{formatSeconds(event.onset_seconds)}</td>
              <td>{formatSeconds(event.offset_seconds)}</td>
              <td>{formatSeconds(event.offset_seconds - event.onset_seconds)}</td>
              <td>{event.velocity}</td>
              <td>{formatNumber(event.confidence)}</td>
              <td aria-describedby="confidence-explanation">
                {event.is_low_confidence ? "Low confidence" : "Regular confidence"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
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

function formatSeconds(value: number): string {
  return `${formatNumber(value)} s`;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 6 }).format(value);
}
