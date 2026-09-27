"use client";

import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

import {
  getTranscriptionRevisionHistory,
  type LoadRevisionHistory,
} from "@/lib/transcription-revisions";
import { RevisionArtifactDownloads } from "./revision-artifact-downloads";

interface LatestRevisionArtifactDownloadsProps {
  jobId: string;
  loadHistory?: LoadRevisionHistory;
  renderDownloads?: (revisionNumber: number) => ReactNode;
}

export function LatestRevisionArtifactDownloads({
  jobId,
  loadHistory = getTranscriptionRevisionHistory,
  renderDownloads,
}: LatestRevisionArtifactDownloadsProps) {
  const [revisionNumber, setRevisionNumber] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const alertRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    queueMicrotask(() => {
      void loadHistory(jobId, controller.signal)
        .then((history) => {
          if (active) setRevisionNumber(history.latest_revision_number);
        })
        .catch(() => {
          if (active && !controller.signal.aborted) {
            setError("The latest revision could not be loaded for downloads.");
          }
        });
    });
    return () => {
      active = false;
      controller.abort();
    };
  }, [jobId, loadHistory]);

  useEffect(() => {
    if (error !== null) alertRef.current?.focus();
  }, [error]);

  if (error !== null) {
    return (
      <div className="error-summary" role="alert" tabIndex={-1} ref={alertRef}>
        {error}
      </div>
    );
  }
  if (revisionNumber === null) {
    return <p aria-live="polite">Loading latest revision for downloads…</p>;
  }
  if (renderDownloads !== undefined) {
    return renderDownloads(revisionNumber);
  }
  return <RevisionArtifactDownloads jobId={jobId} revisionNumber={revisionNumber} />;
}
