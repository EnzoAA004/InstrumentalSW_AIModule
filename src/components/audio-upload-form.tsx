"use client";

import Link from "next/link";
import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from "react";

import {
  INPUT_MODES,
  SAXOPHONE_TYPES,
  TranscriptionApiError,
  submitTranscription,
  type InputMode,
  type SaxophoneType,
  type SubmitTranscription,
  type TranscriptionJob,
} from "@/lib/transcription-api";

interface AudioUploadFormProps {
  submit?: SubmitTranscription;
}

type ViewState = "idle" | "ready" | "submitting" | "success" | "error";

interface ViewError {
  code: string | null;
  message: string;
  field: string | null;
}

const INSTRUMENT_LABELS: Record<SaxophoneType, string> = {
  soprano: "Soprano",
  alto: "Alto",
  tenor: "Tenor",
  baritone: "Baritone",
};

const MODE_LABELS: Record<InputMode, string> = {
  solo: "Solo saxophone",
  mixture: "Mixture",
};

export function AudioUploadForm({ submit = submitTranscription }: AudioUploadFormProps) {
  const [viewState, setViewState] = useState<ViewState>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [saxophoneType, setSaxophoneType] = useState<SaxophoneType>("alto");
  const [inputMode, setInputMode] = useState<InputMode>("solo");
  const [error, setError] = useState<ViewError | null>(null);
  const [job, setJob] = useState<TranscriptionJob | null>(null);
  const alertRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const submittingRef = useRef(false);

  useEffect(() => {
    if (viewState === "error") {
      alertRef.current?.focus();
    }
  }, [viewState, error]);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const candidate = event.currentTarget.files?.[0] ?? null;
    setJob(null);

    if (candidate === null) {
      setFile(null);
      setError(null);
      setViewState("idle");
      return;
    }

    const validationError = validateFile(candidate);
    if (validationError !== null) {
      setFile(null);
      setError(validationError);
      setViewState("error");
      return;
    }

    setFile(candidate);
    setError(null);
    setViewState("ready");
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void performSubmit();
  }

  async function performSubmit() {
    if (submittingRef.current) {
      return;
    }
    if (file === null) {
      showError({
        code: "AUDIO_FILE_REQUIRED",
        message: "Select an MP3 or WAV audio file.",
        field: "file",
      });
      return;
    }

    submittingRef.current = true;
    setError(null);
    setViewState("submitting");
    try {
      const created = await submit({ file, saxophoneType, inputMode });
      setJob(created);
      setViewState("success");
    } catch (caught) {
      if (caught instanceof TranscriptionApiError) {
        showError({
          code: caught.code,
          message: caught.message,
          field: caught.field,
        });
      } else {
        showError({
          code: null,
          message: "An unexpected error prevented the upload. Try again.",
          field: null,
        });
      }
    } finally {
      submittingRef.current = false;
    }
  }

  function showError(nextError: ViewError) {
    setError(nextError);
    setViewState("error");
  }

  function reset() {
    submittingRef.current = false;
    setViewState("idle");
    setFile(null);
    setSaxophoneType("alto");
    setInputMode("solo");
    setError(null);
    setJob(null);
    if (fileInputRef.current !== null) {
      fileInputRef.current.value = "";
    }
  }

  if (viewState === "success" && job !== null) {
    return <CreatedJob job={job} onReset={reset} />;
  }

  const fileErrorDescriptionId = error?.field === "file" ? "upload-error" : undefined;

  return (
    <section className="upload-card" aria-labelledby="upload-title">
      <div className="intro-block">
        <p className="eyebrow">InstrumentalSW</p>
        <h1 id="upload-title">Create a transcription job</h1>
        <p className="intro-copy">
          Select an MP3 or WAV recording, choose the saxophone and audio mode, then send it securely
          through the Saxo product API.
        </p>
      </div>

      {viewState === "error" && error !== null ? (
        <div className="error-summary" id="upload-error" role="alert" tabIndex={-1} ref={alertRef}>
          <h2>We could not create the job</h2>
          <p>{error.message}</p>
          {error.code !== null ? <p className="technical-line">Code: {error.code}</p> : null}
          {error.field !== null ? <p className="technical-line">Field: {error.field}</p> : null}
          {file !== null ? (
            <button className="secondary-button" type="button" onClick={() => void performSubmit()}>
              Try again
            </button>
          ) : null}
        </div>
      ) : null}

      <form className="upload-form" onSubmit={handleSubmit} noValidate>
        <div className="field-group">
          <label htmlFor="audio-file">Audio file</label>
          <input
            ref={fileInputRef}
            id="audio-file"
            name="file"
            type="file"
            accept=".mp3,.wav,audio/mpeg,audio/wav"
            aria-describedby={["file-help", fileErrorDescriptionId].filter(Boolean).join(" ")}
            aria-invalid={fileErrorDescriptionId !== undefined}
            onChange={handleFileChange}
          />
          <p className="field-help" id="file-help">
            MP3 or WAV only. Selecting a file does not upload or play it.
          </p>
          {file !== null ? (
            <div className="file-summary" aria-live="polite">
              <span>{file.name}</span>
              <span>{formatBytes(file.size)}</span>
            </div>
          ) : null}
        </div>

        <div className="form-grid">
          <div className="field-group">
            <label htmlFor="saxophone-type">Saxophone type</label>
            <select
              id="saxophone-type"
              name="saxophone_type"
              value={saxophoneType}
              onChange={(event) => setSaxophoneType(event.target.value as SaxophoneType)}
            >
              {SAXOPHONE_TYPES.map((value) => (
                <option value={value} key={value}>
                  {INSTRUMENT_LABELS[value]}
                </option>
              ))}
            </select>
          </div>

          <div className="field-group">
            <label htmlFor="input-mode">Audio mode</label>
            <select
              id="input-mode"
              name="input_mode"
              value={inputMode}
              aria-describedby="mode-help"
              onChange={(event) => setInputMode(event.target.value as InputMode)}
            >
              {INPUT_MODES.map((value) => (
                <option value={value} key={value}>
                  {MODE_LABELS[value]}
                </option>
              ))}
            </select>
            <p className="field-help" id="mode-help">
              Source separation is not implemented yet. A mixture job can be created, but processing
              a mixed recording is not promised in this story.
            </p>
          </div>
        </div>

        <button className="primary-button" type="submit" disabled={viewState === "submitting"}>
          Create transcription job
        </button>

        {viewState === "submitting" ? (
          <p className="request-status" aria-live="polite">
            Creating transcription job…
          </p>
        ) : null}
      </form>
    </section>
  );
}

function CreatedJob({ job, onReset }: { job: TranscriptionJob; onReset: () => void }) {
  return (
    <section className="upload-card result-card" aria-labelledby="result-title">
      <p className="eyebrow">Saxo</p>
      <h1 id="result-title">Job created</h1>
      <p className="success-copy">
        The Backend accepted the upload and created the transcription job.
      </p>
      <dl className="job-details">
        <Detail label="Job ID" value={job.job_id} />
        <Detail label="Status" value={job.status} />
        <Detail label="Filename" value={job.filename} />
        <Detail label="Size" value={formatBytes(job.size_bytes)} />
        <Detail label="Saxophone" value={job.saxophone_type} />
        <Detail label="Audio mode" value={job.input_mode} />
        <Detail label="Audio SHA-256" value={job.audio_sha256} technical />
      </dl>
      <div className="result-actions">
        <Link className="primary-button" href={`/transcriptions/${job.job_id}`}>
          View job progress
        </Link>
        <button className="secondary-button" type="button" onClick={onReset}>
          Upload another audio file
        </button>
      </div>
    </section>
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

function validateFile(file: File): ViewError | null {
  const lowerName = file.name.toLowerCase();
  if (!lowerName.endsWith(".mp3") && !lowerName.endsWith(".wav")) {
    return {
      code: "UNSUPPORTED_AUDIO_FORMAT",
      message: "Only MP3 and WAV files are supported.",
      field: "file",
    };
  }
  if (file.size === 0) {
    return {
      code: "EMPTY_AUDIO_FILE",
      message: "The selected audio file is empty.",
      field: "file",
    };
  }
  return null;
}

function formatBytes(size: number): string {
  if (size === 1) {
    return "1 byte";
  }
  return `${size.toLocaleString("en-US")} bytes`;
}
