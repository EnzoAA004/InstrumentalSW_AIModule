"use client";

import { useEffect, useRef, useState } from "react";

import { saveVerifiedArtifactBlob } from "@/lib/download-blob";
import {
  downloadRevisionArtifact,
  getRevisionArtifacts,
  TranscriptionArtifactError,
  type DownloadedRevisionArtifact,
  type RevisionArtifactDescriptor,
  type RevisionArtifactList,
} from "@/lib/transcription-artifacts";

export type LoadRevisionArtifacts = (
  jobId: string,
  revisionNumber: number,
  signal?: AbortSignal,
) => Promise<RevisionArtifactList>;
export type DownloadArtifact = (
  jobId: string,
  revisionNumber: number,
  artifactId: string,
  signal?: AbortSignal,
) => Promise<DownloadedRevisionArtifact>;
export type SaveBlob = (blob: Blob, filename: string) => void;

type PanelState = "loading" | "available" | "not_ready" | "downloading" | "downloaded" | "error";

interface RevisionArtifactDownloadsProps {
  jobId: string;
  revisionNumber: number;
  loadArtifacts?: LoadRevisionArtifacts;
  downloadArtifact?: DownloadArtifact;
  saveBlob?: SaveBlob;
}

export function RevisionArtifactDownloads({
  jobId,
  revisionNumber,
  loadArtifacts = getRevisionArtifacts,
  downloadArtifact = downloadRevisionArtifact,
  saveBlob = saveVerifiedArtifactBlob,
}: RevisionArtifactDownloadsProps) {
  const [state, setState] = useState<PanelState>("loading");
  const [listing, setListing] = useState<RevisionArtifactList | null>(null);
  const [activeArtifactId, setActiveArtifactId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const alertRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    queueMicrotask(() => {
      void loadArtifacts(jobId, revisionNumber, controller.signal)
        .then((result) => {
          if (!active) return;
          setListing(result);
          setState(result.artifacts.length === 0 ? "not_ready" : "available");
          setMessage(
            result.artifacts.length === 0
              ? "Artifacts are not available for this revision yet."
              : null,
          );
        })
        .catch((error: unknown) => {
          if (!active || controller.signal.aborted) return;
          if (error instanceof TranscriptionArtifactError && error.code === "ARTIFACTS_NOT_READY") {
            setState("not_ready");
            setMessage("Artifacts are not available for this revision yet.");
            return;
          }
          setState("error");
          setMessage(artifactErrorMessage(error));
        });
    });
    return () => {
      active = false;
      controller.abort();
    };
  }, [jobId, loadArtifacts, revisionNumber]);

  useEffect(() => {
    if (state === "error") alertRef.current?.focus();
  }, [state]);

  async function startDownload(descriptor: RevisionArtifactDescriptor): Promise<void> {
    const controller = new AbortController();
    setActiveArtifactId(descriptor.artifact_id);
    setState("downloading");
    setMessage(`Downloading ${descriptor.filename}…`);
    try {
      const downloaded = await downloadArtifact(
        jobId,
        revisionNumber,
        descriptor.artifact_id,
        controller.signal,
      );
      saveBlob(downloaded.blob, downloaded.filename);
      setState("downloaded");
      setMessage(`Downloaded ${downloaded.filename}.`);
    } catch (error) {
      setState("error");
      setMessage(artifactErrorMessage(error));
    } finally {
      setActiveArtifactId(null);
    }
  }

  return (
    <section
      className="artifact-downloads"
      aria-labelledby={`artifact-downloads-${revisionNumber}`}
    >
      <h2 id={`artifact-downloads-${revisionNumber}`}>Revision artifact downloads</h2>
      <p>Downloads are retrieved through the Saxo product API.</p>
      <p>No public storage URL is exposed.</p>

      {state === "loading" ? <p aria-live="polite">Loading revision artifacts…</p> : null}

      {state === "not_ready" ? (
        <p className="warning-summary" aria-live="polite">
          Artifacts are not available for this revision yet.
        </p>
      ) : null}

      {state === "downloading" || state === "downloaded" ? (
        <p className="request-status" aria-live="polite">
          {message}
        </p>
      ) : null}

      {state === "error" ? (
        <div className="error-summary" role="alert" tabIndex={-1} ref={alertRef}>
          <h3>Download unavailable</h3>
          <p>{message}</p>
        </div>
      ) : null}

      {listing !== null && listing.artifacts.length > 0 ? (
        <ul className="artifact-download-list">
          {listing.artifacts.map((descriptor) => {
            const ownDownload = activeArtifactId === descriptor.artifact_id;
            return (
              <li key={descriptor.artifact_id} className="artifact-download-item">
                <div>
                  <strong>{artifactTypeLabel(descriptor.artifact_type)}</strong>
                  <span className="technical-line">{descriptor.filename}</span>
                  <span>{formatBytes(descriptor.size_bytes)}</span>
                  <span aria-hidden="true">{abbreviateSha(descriptor.sha256)}</span>
                  <span className="technical-line">{descriptor.sha256}</span>
                </div>
                <button
                  type="button"
                  className="secondary-button"
                  disabled={ownDownload}
                  onClick={() => void startDownload(descriptor)}
                >
                  {ownDownload
                    ? `Downloading ${artifactTypeLabel(descriptor.artifact_type)}…`
                    : `Download ${artifactTypeLabel(descriptor.artifact_type)} ${descriptor.filename}`}
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}

function artifactTypeLabel(value: RevisionArtifactDescriptor["artifact_type"]): string {
  if (value === "midi") return "MIDI";
  if (value === "musicxml") return "MusicXML";
  return "SVG";
}

function formatBytes(value: number): string {
  return `${new Intl.NumberFormat("en-US").format(value)} bytes`;
}

function abbreviateSha(value: string): string {
  return `${value.slice(0, 12)}…`;
}

function artifactErrorMessage(error: unknown): string {
  return error instanceof TranscriptionArtifactError
    ? error.message
    : "The artifact could not be downloaded safely.";
}
