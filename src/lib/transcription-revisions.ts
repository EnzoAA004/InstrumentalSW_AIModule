import { SAXOPHONE_TYPES, TranscriptionApiError, type SaxophoneType } from "./transcription-api";

export type EventOrigin = "model" | "human";
export type DerivedArtifactsStatus = "CURRENT" | "STALE" | "REGENERATION_REQUESTED";

export interface TranscriptionRevisionEvent {
  event_id: string;
  origin: EventOrigin;
  source_index: number | null;
  pitch_concert_midi: number;
  written_pitch_midi: number;
  onset_seconds: number;
  offset_seconds: number;
  velocity: number;
  confidence: number | null;
  is_low_confidence: boolean | null;
}

export interface TranscriptionRevisionSummary {
  event_count: number;
  model_event_count: number;
  human_event_count: number;
}

export interface TranscriptionRevision {
  job_id: string;
  revision_number: number;
  parent_revision_number: number | null;
  created_at: string;
  saxophone_type: SaxophoneType;
  events: TranscriptionRevisionEvent[];
  summary: TranscriptionRevisionSummary;
  derived_artifacts_status: DerivedArtifactsStatus;
  schema_version: "1.0";
}

export interface TranscriptionRevisionHistoryEntry {
  revision_number: number;
  parent_revision_number: number | null;
  created_at: string;
  event_count: number;
  model_event_count: number;
  human_event_count: number;
  derived_artifacts_status: DerivedArtifactsStatus;
}

export interface TranscriptionRevisionHistory {
  job_id: string;
  latest_revision_number: number;
  revision_count: number;
  revisions: TranscriptionRevisionHistoryEntry[];
}

export interface RevisionUpdateOperation {
  type: "update";
  event_id: string;
  written_pitch_midi: number;
  onset_seconds: number;
  offset_seconds: number;
}

export interface RevisionAddOperation {
  type: "add";
  written_pitch_midi: number;
  onset_seconds: number;
  offset_seconds: number;
  velocity?: number;
}

export interface RevisionDeleteOperation {
  type: "delete";
  event_id: string;
}

export type RevisionOperation =
  RevisionUpdateOperation | RevisionAddOperation | RevisionDeleteOperation;

export interface RevisionCreateCommand {
  base_revision_number: number;
  operations: RevisionOperation[];
}

export interface RegenerationRequest {
  request_id: string;
  job_id: string;
  revision_number: number;
  status: "REQUESTED";
  requested_artifacts: readonly ["midi", "musicxml", "svg"];
}

export interface DraftRevisionEvent {
  event_id: string;
  origin: EventOrigin;
  source_index: number | null;
  written_pitch_midi: string;
  onset_seconds: string;
  offset_seconds: string;
  velocity: string;
  confidence: number | null;
  is_low_confidence: boolean | null;
}

export interface ValidatedDraftEvent extends DraftRevisionEvent {
  pitch_concert_midi: number | null;
  parsed_written_pitch_midi: number | null;
  parsed_onset_seconds: number | null;
  parsed_offset_seconds: number | null;
  parsed_velocity: number | null;
}

export interface DraftValidationResult {
  isValid: boolean;
  errors: Record<string, string>;
  events: ValidatedDraftEvent[];
}

export type LoadRevisionHistory = (
  jobId: string,
  signal?: AbortSignal,
) => Promise<TranscriptionRevisionHistory>;
export type LoadRevision = (
  jobId: string,
  revisionNumber: number,
  signal?: AbortSignal,
) => Promise<TranscriptionRevision>;
export type SaveRevision = (
  jobId: string,
  command: RevisionCreateCommand,
  signal?: AbortSignal,
) => Promise<TranscriptionRevision>;
export type RequestRegeneration = (
  jobId: string,
  revisionNumber: number,
  signal?: AbortSignal,
) => Promise<RegenerationRequest>;

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const LOCAL_BACKEND_URL = "http://localhost:8080";
const TRANSCRIPTIONS_PATH = "/api/v1/transcriptions";
const OFFSETS: Record<SaxophoneType, number> = {
  soprano: 2,
  alto: 9,
  tenor: 14,
  baritone: 21,
};

export async function getTranscriptionRevisionHistory(
  jobId: string,
  signal?: AbortSignal,
): Promise<TranscriptionRevisionHistory> {
  validateJobId(jobId);
  const response = await safeFetch(`${revisionBaseUrl(jobId)}`, { method: "GET", signal }, signal);
  const payload = await readJson(response);
  throwPublicError(response, payload, 200);
  if (!isRevisionHistory(payload, jobId)) throw invalidResponse(response.status);
  return payload;
}

export async function getTranscriptionRevision(
  jobId: string,
  revisionNumber: number,
  signal?: AbortSignal,
): Promise<TranscriptionRevision> {
  validateJobId(jobId);
  validateRevisionNumber(revisionNumber);
  const response = await safeFetch(
    `${revisionBaseUrl(jobId)}/${revisionNumber}`,
    { method: "GET", signal },
    signal,
  );
  const payload = await readJson(response);
  throwPublicError(response, payload, 200);
  if (!isRevision(payload, jobId, revisionNumber)) throw invalidResponse(response.status);
  return payload;
}

export async function createTranscriptionRevision(
  jobId: string,
  command: RevisionCreateCommand,
  signal?: AbortSignal,
): Promise<TranscriptionRevision> {
  validateJobId(jobId);
  validateCommand(command);
  const response = await safeFetch(
    revisionBaseUrl(jobId),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(command),
      signal,
    },
    signal,
  );
  const payload = await readJson(response);
  throwPublicError(response, payload, 201);
  if (!isRevision(payload, jobId, command.base_revision_number + 1)) {
    throw invalidResponse(response.status);
  }
  return payload;
}

export async function requestArtifactRegeneration(
  jobId: string,
  revisionNumber: number,
  signal?: AbortSignal,
): Promise<RegenerationRequest> {
  validateJobId(jobId);
  validateRevisionNumber(revisionNumber);
  const response = await safeFetch(
    `${revisionBaseUrl(jobId)}/${revisionNumber}/regeneration-requests`,
    { method: "POST", signal },
    signal,
  );
  const payload = await readJson(response);
  throwPublicError(response, payload, 202);
  if (!isRegenerationRequest(payload, jobId, revisionNumber)) {
    throw invalidResponse(response.status);
  }
  return payload;
}

export function revisionToDraftEvents(revision: TranscriptionRevision): DraftRevisionEvent[] {
  return revision.events.map((event) => ({
    event_id: event.event_id,
    origin: event.origin,
    source_index: event.source_index,
    written_pitch_midi: String(event.written_pitch_midi),
    onset_seconds: String(event.onset_seconds),
    offset_seconds: String(event.offset_seconds),
    velocity: String(event.velocity),
    confidence: event.confidence,
    is_low_confidence: event.is_low_confidence,
  }));
}

export function validateDraftEvents(
  draftEvents: DraftRevisionEvent[],
  saxophoneType: SaxophoneType,
): DraftValidationResult {
  const errors: Record<string, string> = {};
  const counts = new Map<string, number>();
  for (const event of draftEvents)
    counts.set(event.event_id, (counts.get(event.event_id) ?? 0) + 1);

  const events = draftEvents.map((event): ValidatedDraftEvent => {
    const prefix = event.event_id;
    if (!event.event_id || (counts.get(event.event_id) ?? 0) > 1) {
      errors[`${prefix}.event_id`] = event.event_id
        ? "Event ID must be unique."
        : "Event ID is required.";
    }
    if (event.origin !== "model" && event.origin !== "human") {
      errors[`${prefix}.origin`] = "Event origin is invalid.";
    }

    const written = parseRequiredInteger(
      event.written_pitch_midi,
      `${prefix}.written_pitch_midi`,
      "Written MIDI is required.",
      "Written MIDI must be an integer from 0 to 127.",
      errors,
    );
    let concert: number | null = null;
    if (written !== null) {
      concert = written - OFFSETS[saxophoneType];
      if (concert < 0 || concert > 127) {
        errors[`${prefix}.written_pitch_midi`] =
          "Concert MIDI derived from written pitch must be from 0 to 127.";
        concert = null;
      }
    }

    const onset = parseRequiredNumber(
      event.onset_seconds,
      `${prefix}.onset_seconds`,
      "Onset is required.",
      "Onset must be a finite non-negative number.",
      errors,
    );
    if (onset !== null && onset < 0) {
      errors[`${prefix}.onset_seconds`] = "Onset must be a finite non-negative number.";
    }
    const offset = parseRequiredNumber(
      event.offset_seconds,
      `${prefix}.offset_seconds`,
      "Offset is required.",
      "Offset must be a finite number.",
      errors,
    );
    if (onset !== null && offset !== null && offset <= onset) {
      errors[`${prefix}.offset_seconds`] = "Offset must be greater than onset.";
    }
    const velocity = parseRequiredInteger(
      event.velocity,
      `${prefix}.velocity`,
      "Velocity is required.",
      "Velocity must be an integer from 0 to 127.",
      errors,
    );

    return {
      ...event,
      pitch_concert_midi: concert,
      parsed_written_pitch_midi: written,
      parsed_onset_seconds: onset,
      parsed_offset_seconds: offset,
      parsed_velocity: velocity,
    };
  });
  return { isValid: Object.keys(errors).length === 0, errors, events };
}

export function buildRevisionOperations(
  serverRevision: TranscriptionRevision,
  draftEvents: DraftRevisionEvent[],
): RevisionOperation[] {
  const validation = validateDraftEvents(draftEvents, serverRevision.saxophone_type);
  if (!validation.isValid) {
    throw new TranscriptionApiError(
      "INVALID_REVISION_EVENT",
      "The local draft contains invalid events.",
      "operations",
      422,
    );
  }
  const serverById = new Map(serverRevision.events.map((event) => [event.event_id, event]));
  const draftById = new Map(draftEvents.map((event) => [event.event_id, event]));
  const operations: RevisionOperation[] = [];

  for (const source of serverRevision.events) {
    const draft = draftById.get(source.event_id);
    if (!draft) {
      operations.push({ type: "delete", event_id: source.event_id });
      continue;
    }
    const written = Number(draft.written_pitch_midi);
    const onset = Number(draft.onset_seconds);
    const offset = Number(draft.offset_seconds);
    if (
      written !== source.written_pitch_midi ||
      onset !== source.onset_seconds ||
      offset !== source.offset_seconds
    ) {
      operations.push({
        type: "update",
        event_id: source.event_id,
        written_pitch_midi: written,
        onset_seconds: onset,
        offset_seconds: offset,
      });
    }
  }
  for (const draft of draftEvents) {
    if (serverById.has(draft.event_id)) continue;
    operations.push({
      type: "add",
      written_pitch_midi: Number(draft.written_pitch_midi),
      onset_seconds: Number(draft.onset_seconds),
      offset_seconds: Number(draft.offset_seconds),
      velocity: Number(draft.velocity),
    });
  }
  return operations;
}

function parseRequiredInteger(
  raw: string,
  key: string,
  requiredMessage: string,
  invalidMessage: string,
  errors: Record<string, string>,
): number | null {
  if (raw.trim() === "") {
    errors[key] = requiredMessage;
    return null;
  }
  const parsed = Number(raw);
  if (!Number.isInteger(parsed) || parsed < 0 || parsed > 127) {
    errors[key] = invalidMessage;
    return null;
  }
  return parsed;
}

function parseRequiredNumber(
  raw: string,
  key: string,
  requiredMessage: string,
  invalidMessage: string,
  errors: Record<string, string>,
): number | null {
  if (raw.trim() === "") {
    errors[key] = requiredMessage;
    return null;
  }
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) {
    errors[key] = invalidMessage;
    return null;
  }
  return parsed;
}

function validateCommand(command: RevisionCreateCommand): void {
  if (
    !Number.isSafeInteger(command.base_revision_number) ||
    command.base_revision_number < 0 ||
    !Array.isArray(command.operations) ||
    command.operations.length === 0
  ) {
    throw new TranscriptionApiError(
      "INVALID_REVISION_OPERATION",
      "A non-empty revision operation batch is required.",
      "operations",
      422,
    );
  }
}

async function safeFetch(url: string, init: RequestInit, signal?: AbortSignal): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new TranscriptionApiError(
      "BACKEND_UNAVAILABLE",
      "The Saxo service is currently unavailable. Try again.",
      null,
      null,
    );
  }
}

function throwPublicError(response: Response, payload: unknown, expectedStatus: number): void {
  if (response.status === expectedStatus) return;
  if (isPublicError(payload)) {
    throw new TranscriptionApiError(payload.code, payload.message, payload.field, response.status);
  }
  throw invalidResponse(response.status);
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    throw invalidResponse(response.status);
  }
}

function revisionBaseUrl(jobId: string): string {
  const configured = process.env.NEXT_PUBLIC_SAXO_API_BASE_URL?.trim();
  const base = (configured || LOCAL_BACKEND_URL).replace(/\/+$/, "");
  return `${base}${TRANSCRIPTIONS_PATH}/${encodeURIComponent(jobId)}/revisions`;
}

function validateJobId(jobId: string): void {
  if (!UUID_PATTERN.test(jobId)) {
    throw new TranscriptionApiError(
      "INVALID_JOB_ID",
      "Job ID must be a valid UUID.",
      "job_id",
      400,
    );
  }
}

function validateRevisionNumber(value: number): void {
  if (!Number.isSafeInteger(value) || value < 0) {
    throw new TranscriptionApiError(
      "REVISION_NOT_FOUND",
      "Transcription revision not found.",
      "revision_number",
      404,
    );
  }
}

function invalidResponse(status: number | null): TranscriptionApiError {
  return new TranscriptionApiError(
    "INVALID_BACKEND_RESPONSE",
    "The Saxo service returned an invalid response.",
    null,
    status,
  );
}

function isRevisionHistory(value: unknown, jobId: string): value is TranscriptionRevisionHistory {
  if (!hasExactKeys(value, ["job_id", "latest_revision_number", "revision_count", "revisions"])) {
    return false;
  }
  if (
    typeof value.job_id !== "string" ||
    value.job_id.toLowerCase() !== jobId.toLowerCase() ||
    !isNonNegativeInteger(value.latest_revision_number) ||
    !isNonNegativeInteger(value.revision_count) ||
    value.revision_count < 1 ||
    !Array.isArray(value.revisions) ||
    value.revisions.length !== value.revision_count ||
    value.latest_revision_number !== value.revision_count - 1
  ) {
    return false;
  }
  return value.revisions.every((entry, index) => isHistoryEntry(entry, index));
}

function isHistoryEntry(value: unknown, index: number): value is TranscriptionRevisionHistoryEntry {
  if (
    !hasExactKeys(value, [
      "revision_number",
      "parent_revision_number",
      "created_at",
      "event_count",
      "model_event_count",
      "human_event_count",
      "derived_artifacts_status",
    ])
  ) {
    return false;
  }
  return (
    value.revision_number === index &&
    value.parent_revision_number === (index === 0 ? null : index - 1) &&
    isInstant(value.created_at) &&
    isNonNegativeInteger(value.event_count) &&
    isNonNegativeInteger(value.model_event_count) &&
    isNonNegativeInteger(value.human_event_count) &&
    value.event_count === value.model_event_count + value.human_event_count &&
    isDerivedStatus(value.derived_artifacts_status)
  );
}

function isRevision(
  value: unknown,
  jobId: string,
  revisionNumber: number,
): value is TranscriptionRevision {
  if (
    !hasExactKeys(value, [
      "job_id",
      "revision_number",
      "parent_revision_number",
      "created_at",
      "saxophone_type",
      "events",
      "summary",
      "derived_artifacts_status",
      "schema_version",
    ]) ||
    !hasExactKeys(value.summary, ["event_count", "model_event_count", "human_event_count"])
  ) {
    return false;
  }
  if (
    typeof value.job_id !== "string" ||
    value.job_id.toLowerCase() !== jobId.toLowerCase() ||
    value.revision_number !== revisionNumber ||
    value.parent_revision_number !== (revisionNumber === 0 ? null : revisionNumber - 1) ||
    !isInstant(value.created_at) ||
    typeof value.saxophone_type !== "string" ||
    !SAXOPHONE_TYPES.includes(value.saxophone_type as SaxophoneType) ||
    !Array.isArray(value.events) ||
    !isDerivedStatus(value.derived_artifacts_status) ||
    value.schema_version !== "1.0" ||
    !isNonNegativeInteger(value.summary.event_count) ||
    !isNonNegativeInteger(value.summary.model_event_count) ||
    !isNonNegativeInteger(value.summary.human_event_count) ||
    value.summary.event_count !== value.events.length ||
    value.summary.event_count !== value.summary.model_event_count + value.summary.human_event_count
  ) {
    return false;
  }
  const ids = new Set<string>();
  let modelCount = 0;
  for (const event of value.events) {
    if (!isRevisionEvent(event, value.saxophone_type as SaxophoneType) || ids.has(event.event_id)) {
      return false;
    }
    ids.add(event.event_id);
    if (event.origin === "model") modelCount += 1;
  }
  return modelCount === value.summary.model_event_count;
}

function isRevisionEvent(
  value: unknown,
  saxophone: SaxophoneType,
): value is TranscriptionRevisionEvent {
  if (
    !hasExactKeys(value, [
      "event_id",
      "origin",
      "source_index",
      "pitch_concert_midi",
      "written_pitch_midi",
      "onset_seconds",
      "offset_seconds",
      "velocity",
      "confidence",
      "is_low_confidence",
    ]) ||
    typeof value.event_id !== "string" ||
    (value.origin !== "model" && value.origin !== "human") ||
    !isMidi(value.pitch_concert_midi) ||
    !isMidi(value.written_pitch_midi) ||
    value.pitch_concert_midi !== value.written_pitch_midi - OFFSETS[saxophone] ||
    !isFiniteNumber(value.onset_seconds) ||
    value.onset_seconds < 0 ||
    !isFiniteNumber(value.offset_seconds) ||
    value.offset_seconds <= value.onset_seconds ||
    !isMidi(value.velocity)
  ) {
    return false;
  }
  if (value.origin === "model") {
    return (
      isNonNegativeInteger(value.source_index) &&
      value.event_id === `source-${value.source_index}` &&
      isUnitInterval(value.confidence) &&
      typeof value.is_low_confidence === "boolean"
    );
  }
  return (
    value.source_index === null &&
    value.confidence === null &&
    value.is_low_confidence === null &&
    /^human-[0-9a-f-]{36}$/i.test(value.event_id)
  );
}

function isRegenerationRequest(
  value: unknown,
  jobId: string,
  revisionNumber: number,
): value is RegenerationRequest {
  return (
    hasExactKeys(value, [
      "request_id",
      "job_id",
      "revision_number",
      "status",
      "requested_artifacts",
    ]) &&
    typeof value.request_id === "string" &&
    UUID_PATTERN.test(value.request_id) &&
    typeof value.job_id === "string" &&
    value.job_id.toLowerCase() === jobId.toLowerCase() &&
    value.revision_number === revisionNumber &&
    value.status === "REQUESTED" &&
    Array.isArray(value.requested_artifacts) &&
    JSON.stringify(value.requested_artifacts) === JSON.stringify(["midi", "musicxml", "svg"])
  );
}

function isPublicError(
  value: unknown,
): value is { code: string; message: string; field: string | null } {
  return (
    hasExactKeys(value, ["code", "message", "field"]) &&
    typeof value.code === "string" &&
    value.code.length > 0 &&
    typeof value.message === "string" &&
    value.message.length > 0 &&
    (value.field === null || typeof value.field === "string")
  );
}

function hasExactKeys(value: unknown, keys: string[]): value is Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return JSON.stringify(actual) === JSON.stringify(expected);
}

function isInstant(value: unknown): value is string {
  return typeof value === "string" && Number.isFinite(Date.parse(value));
}

function isMidi(value: unknown): value is number {
  return Number.isInteger(value) && typeof value === "number" && value >= 0 && value <= 127;
}

function isNonNegativeInteger(value: unknown): value is number {
  return Number.isSafeInteger(value) && typeof value === "number" && value >= 0;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isUnitInterval(value: unknown): value is number {
  return isFiniteNumber(value) && value >= 0 && value <= 1;
}

function isDerivedStatus(value: unknown): value is DerivedArtifactsStatus {
  return value === "CURRENT" || value === "STALE" || value === "REGENERATION_REQUESTED";
}
