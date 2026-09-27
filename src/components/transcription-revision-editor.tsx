"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { RevisionArtifactDownloads } from "@/components/revision-artifact-downloads";
import { TranscriptionApiError } from "@/lib/transcription-api";
import {
  buildRevisionOperations,
  createTranscriptionRevision,
  getTranscriptionRevision,
  getTranscriptionRevisionHistory,
  requestArtifactRegeneration,
  revisionToDraftEvents,
  validateDraftEvents,
  type DraftRevisionEvent,
  type LoadRevision,
  type LoadRevisionHistory,
  type RequestRegeneration,
  type SaveRevision,
  type TranscriptionRevision,
  type TranscriptionRevisionHistory,
} from "@/lib/transcription-revisions";

interface TranscriptionRevisionEditorProps {
  jobId: string;
  loadHistory?: LoadRevisionHistory;
  loadRevision?: LoadRevision;
  saveRevision?: SaveRevision;
  requestRegeneration?: RequestRegeneration;
}

type EditorState = "loading" | "ready" | "not_ready" | "not_found" | "error";
type SaveState = "idle" | "saving" | "conflict" | "saved";

export function TranscriptionRevisionEditor({
  jobId,
  loadHistory = getTranscriptionRevisionHistory,
  loadRevision = getTranscriptionRevision,
  saveRevision = createTranscriptionRevision,
  requestRegeneration = requestArtifactRegeneration,
}: TranscriptionRevisionEditorProps) {
  const [state, setState] = useState<EditorState>("loading");
  const [history, setHistory] = useState<TranscriptionRevisionHistory | null>(null);
  const [serverRevision, setServerRevision] = useState<TranscriptionRevision | null>(null);
  const [selectedRevision, setSelectedRevision] = useState<number | null>(null);
  const [draftEvents, setDraftEvents] = useState<DraftRevisionEvent[]>([]);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [regenerationMessage, setRegenerationMessage] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const alertRef = useRef<HTMLDivElement>(null);
  const localIdRef = useRef(0);
  const showArtifactDownloads =
    loadHistory === getTranscriptionRevisionHistory && loadRevision === getTranscriptionRevision;

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    queueMicrotask(() => {
      void loadHistory(jobId, controller.signal)
        .then(async (loadedHistory) => {
          const revision = await loadRevision(
            jobId,
            loadedHistory.latest_revision_number,
            controller.signal,
          );
          if (!active) return;
          setHistory(loadedHistory);
          setServerRevision(revision);
          setSelectedRevision(revision.revision_number);
          setDraftEvents(revisionToDraftEvents(revision));
          setState("ready");
        })
        .catch((error: unknown) => {
          if (!active || controller.signal.aborted) return;
          setMessage(errorMessage(error));
          setState(errorState(error));
        });
    });
    return () => {
      active = false;
      controller.abort();
    };
  }, [jobId, loadHistory, loadRevision]);

  useEffect(() => {
    if (
      state === "error" ||
      state === "not_found" ||
      state === "not_ready" ||
      saveState === "conflict"
    ) {
      alertRef.current?.focus();
    }
  }, [state, saveState]);

  const validation = useMemo(
    () =>
      serverRevision === null
        ? { isValid: false, errors: {}, events: [] }
        : validateDraftEvents(draftEvents, serverRevision.saxophone_type),
    [draftEvents, serverRevision],
  );
  const isLatest =
    history !== null &&
    selectedRevision !== null &&
    selectedRevision === history.latest_revision_number;
  const operations = useMemo(() => {
    if (serverRevision === null || !validation.isValid || !isLatest) return [];
    try {
      return buildRevisionOperations(serverRevision, draftEvents);
    } catch {
      return [];
    }
  }, [draftEvents, isLatest, serverRevision, validation.isValid]);
  const canSave = validation.isValid && isLatest && operations.length > 0 && saveState !== "saving";

  function updateField(eventId: string, field: keyof DraftRevisionEvent, value: string) {
    setDraftEvents((current) =>
      current.map((event) => (event.event_id === eventId ? { ...event, [field]: value } : event)),
    );
    setSaveState("idle");
    setMessage(null);
  }

  function addNote() {
    localIdRef.current += 1;
    setDraftEvents((current) => [
      ...current,
      {
        event_id: `draft-human-${localIdRef.current}`,
        origin: "human",
        source_index: null,
        written_pitch_midi: "69",
        onset_seconds: "0",
        offset_seconds: "0.5",
        velocity: "64",
        confidence: null,
        is_low_confidence: null,
      },
    ]);
    setSaveState("idle");
  }

  function deleteEvent(eventId: string) {
    setDraftEvents((current) => current.filter((event) => event.event_id !== eventId));
    setConfirmDeleteId(null);
    setSaveState("idle");
  }

  function discard() {
    if (serverRevision === null) return;
    setDraftEvents(revisionToDraftEvents(serverRevision));
    setConfirmDeleteId(null);
    setSaveState("idle");
    setMessage(null);
  }

  async function save() {
    if (!canSave || serverRevision === null) return;
    const controller = new AbortController();
    setSaveState("saving");
    setMessage(null);
    try {
      const created = await saveRevision(
        jobId,
        {
          base_revision_number: serverRevision.revision_number,
          operations,
        },
        controller.signal,
      );
      setServerRevision(created);
      setSelectedRevision(created.revision_number);
      setDraftEvents(revisionToDraftEvents(created));
      setHistory((current) => appendHistory(current, created));
      setSaveState("saved");
      setRegenerationMessage(false);
    } catch (error) {
      setMessage(errorMessage(error));
      setSaveState(
        error instanceof TranscriptionApiError && error.code === "REVISION_CONFLICT"
          ? "conflict"
          : "idle",
      );
    }
  }

  async function reloadLatest() {
    const controller = new AbortController();
    setState("loading");
    setMessage(null);
    try {
      const loadedHistory = await loadHistory(jobId, controller.signal);
      const latest = await loadRevision(
        jobId,
        loadedHistory.latest_revision_number,
        controller.signal,
      );
      setHistory(loadedHistory);
      setServerRevision(latest);
      setSelectedRevision(latest.revision_number);
      setDraftEvents(revisionToDraftEvents(latest));
      setSaveState("idle");
      setState("ready");
    } catch (error) {
      setMessage(errorMessage(error));
      setState(errorState(error));
    }
  }

  async function chooseRevision(value: string) {
    if (history === null) return;
    const revisionNumber = Number(value);
    const controller = new AbortController();
    try {
      const loaded = await loadRevision(jobId, revisionNumber, controller.signal);
      setServerRevision(loaded);
      setSelectedRevision(revisionNumber);
      setDraftEvents(revisionToDraftEvents(loaded));
      setSaveState("idle");
      setMessage(null);
      setRegenerationMessage(false);
    } catch (error) {
      setMessage(errorMessage(error));
      setState(errorState(error));
    }
  }

  async function regenerate() {
    if (serverRevision === null) return;
    const controller = new AbortController();
    try {
      await requestRegeneration(jobId, serverRevision.revision_number, controller.signal);
      setRegenerationMessage(true);
      setServerRevision({
        ...serverRevision,
        derived_artifacts_status: "REGENERATION_REQUESTED",
      });
    } catch (error) {
      setMessage(errorMessage(error));
    }
  }

  return (
    <section className="upload-card revision-editor-card" aria-labelledby="revision-editor-title">
      <p className="eyebrow">InstrumentalSW</p>
      <h1 id="revision-editor-title">Edit transcription notes</h1>
      <p className="technical-value">Job ID: {jobId}</p>

      {state === "loading" ? (
        <p aria-live="polite" className="request-status">
          Loading revision editor…
        </p>
      ) : null}

      {message !== null ? (
        <div className="error-summary" role="alert" tabIndex={-1} ref={alertRef}>
          <h2>{saveState === "conflict" ? "Revision conflict" : "Revision unavailable"}</h2>
          <p>{message}</p>
          {saveState === "conflict" ? (
            <button className="secondary-button" type="button" onClick={() => void reloadLatest()}>
              Reload latest revision
            </button>
          ) : null}
        </div>
      ) : null}

      {state === "ready" && history !== null && serverRevision !== null ? (
        <>
          <label className="field-label" htmlFor="revision-history">
            Revision history
          </label>
          <select
            id="revision-history"
            value={selectedRevision ?? history.latest_revision_number}
            onChange={(event) => void chooseRevision(event.target.value)}
          >
            {history.revisions.map((entry) => (
              <option key={entry.revision_number} value={entry.revision_number}>
                {entry.revision_number === 0
                  ? "Revision 0 — original"
                  : `Revision ${entry.revision_number}`}
              </option>
            ))}
          </select>

          {!isLatest ? (
            <p className="warning-summary">Historical revisions are read-only.</p>
          ) : null}

          <p className="review-summary" aria-live="polite">
            Revision {serverRevision.revision_number} · {draftEvents.length} events
          </p>

          {Object.keys(validation.errors).length > 0 ? (
            <div className="error-summary compact-error-summary" role="alert">
              Correct the highlighted event fields before saving.
            </div>
          ) : null}

          <div className="review-table-scroll">
            <table aria-label="Editable note events" className="revision-editor-table">
              <thead>
                <tr>
                  <th>Event</th>
                  <th>Written MIDI</th>
                  <th>Concert MIDI</th>
                  <th>Onset</th>
                  <th>Offset</th>
                  <th>Velocity</th>
                  <th>Confidence</th>
                  <th>Confidence status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {draftEvents.map((event, index) => {
                  const validated = validation.events[index];
                  const readOnly = !isLatest;
                  return (
                    <tr key={event.event_id}>
                      <td>
                        <strong>
                          {event.origin === "model" ? "Model event" : "Human-added event"}
                        </strong>
                        <span className="technical-line">{event.event_id}</span>
                      </td>
                      <EditorNumberField
                        event={event}
                        field="written_pitch_midi"
                        label={`Written MIDI for ${event.event_id}`}
                        error={validation.errors[`${event.event_id}.written_pitch_midi`]}
                        disabled={readOnly}
                        onChange={updateField}
                      />
                      <td>Concert MIDI: {validated?.pitch_concert_midi ?? "Invalid"}</td>
                      <EditorNumberField
                        event={event}
                        field="onset_seconds"
                        label={`Onset for ${event.event_id}`}
                        error={validation.errors[`${event.event_id}.onset_seconds`]}
                        disabled={readOnly}
                        onChange={updateField}
                      />
                      <EditorNumberField
                        event={event}
                        field="offset_seconds"
                        label={`Offset for ${event.event_id}`}
                        error={validation.errors[`${event.event_id}.offset_seconds`]}
                        disabled={readOnly}
                        onChange={updateField}
                      />
                      <td>{event.velocity}</td>
                      <td>{event.origin === "human" ? "Not applicable" : event.confidence}</td>
                      <td>
                        {event.origin === "human"
                          ? "Human edit"
                          : event.is_low_confidence
                            ? "Low confidence"
                            : "Regular confidence"}
                      </td>
                      <td>
                        {isLatest ? (
                          confirmDeleteId === event.event_id ? (
                            <button
                              type="button"
                              className="danger-button"
                              onClick={() => deleteEvent(event.event_id)}
                            >
                              Confirm delete {event.event_id}
                            </button>
                          ) : (
                            <button
                              type="button"
                              className="secondary-button"
                              onClick={() => setConfirmDeleteId(event.event_id)}
                            >
                              Delete {event.event_id}
                            </button>
                          )
                        ) : (
                          "Read-only"
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {isLatest ? (
            <div className="progress-actions editor-actions">
              <button type="button" className="secondary-button" onClick={addNote}>
                Add note
              </button>
              <button type="button" className="secondary-button" onClick={discard}>
                Discard local changes
              </button>
              <button
                type="button"
                className="primary-button"
                disabled={!canSave}
                onClick={() => void save()}
              >
                Save revision
              </button>
            </div>
          ) : null}

          {serverRevision.derived_artifacts_status === "STALE" ? (
            <div className="warning-summary regeneration-summary">
              <p>Derived artifacts are stale.</p>
              <button type="button" className="secondary-button" onClick={() => void regenerate()}>
                Request artifact regeneration
              </button>
            </div>
          ) : null}

          {regenerationMessage ||
          serverRevision.derived_artifacts_status === "REGENERATION_REQUESTED" ? (
            <div className="success-summary" aria-live="polite">
              <p>Regeneration requested.</p>
              <p>No processing worker is connected yet.</p>
            </div>
          ) : null}

          {showArtifactDownloads ? (
            <RevisionArtifactDownloads
              jobId={jobId}
              revisionNumber={serverRevision.revision_number}
            />
          ) : null}
        </>
      ) : null}

      <nav className="progress-actions" aria-label="Revision editor navigation">
        <Link className="text-link" href={`/transcriptions/${jobId}/review/playback`}>
          Play synchronized review
        </Link>
        <Link className="text-link" href={`/transcriptions/${jobId}/review`}>
          Back to read-only review
        </Link>
        <Link className="text-link" href={`/transcriptions/${jobId}`}>
          Back to job progress
        </Link>
      </nav>
    </section>
  );
}

function EditorNumberField({
  event,
  field,
  label,
  error,
  disabled,
  onChange,
}: {
  event: DraftRevisionEvent;
  field: "written_pitch_midi" | "onset_seconds" | "offset_seconds";
  label: string;
  error?: string;
  disabled: boolean;
  onChange: (eventId: string, field: keyof DraftRevisionEvent, value: string) => void;
}) {
  const errorId = `${event.event_id}-${field}-error`;
  return (
    <td>
      <label className="visually-hidden" htmlFor={`${event.event_id}-${field}`}>
        {label}
      </label>
      <input
        id={`${event.event_id}-${field}`}
        type="number"
        value={event[field]}
        disabled={disabled}
        aria-label={label}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        onChange={(input) => onChange(event.event_id, field, input.target.value)}
      />
      {error ? (
        <span id={errorId} className="field-error">
          {error}
        </span>
      ) : null}
    </td>
  );
}

function appendHistory(
  history: TranscriptionRevisionHistory | null,
  revision: TranscriptionRevision,
): TranscriptionRevisionHistory {
  const entry = {
    revision_number: revision.revision_number,
    parent_revision_number: revision.parent_revision_number,
    created_at: revision.created_at,
    event_count: revision.summary.event_count,
    model_event_count: revision.summary.model_event_count,
    human_event_count: revision.summary.human_event_count,
    derived_artifacts_status: revision.derived_artifacts_status,
  };
  return {
    job_id: revision.job_id,
    latest_revision_number: revision.revision_number,
    revision_count: (history?.revision_count ?? revision.revision_number) + 1,
    revisions: [...(history?.revisions ?? []), entry],
  };
}

function errorState(error: unknown): EditorState {
  if (error instanceof TranscriptionApiError) {
    if (error.code === "TRANSCRIPTION_RESULT_NOT_READY") return "not_ready";
    if (error.code === "TRANSCRIPTION_NOT_FOUND") return "not_found";
  }
  return "error";
}

function errorMessage(error: unknown): string {
  return error instanceof TranscriptionApiError
    ? error.message
    : "An unexpected error prevented the revision editor from loading.";
}
