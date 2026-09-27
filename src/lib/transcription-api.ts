export const SAXOPHONE_TYPES = ["soprano", "alto", "tenor", "baritone"] as const;
export const INPUT_MODES = ["solo", "mixture"] as const;

export type SaxophoneType = (typeof SAXOPHONE_TYPES)[number];
export type InputMode = (typeof INPUT_MODES)[number];

export interface TranscriptionJob {
  job_id: string;
  status: string;
  filename: string;
  size_bytes: number;
  audio_sha256: string;
  saxophone_type: SaxophoneType;
  input_mode: InputMode;
}

export interface TranscriptionReviewEvent {
  index: number;
  pitch_concert_midi: number;
  written_pitch_midi: number;
  onset_seconds: number;
  offset_seconds: number;
  velocity: number;
  confidence: number;
  is_low_confidence: boolean;
}

export interface TranscriptionReview {
  job_id: string;
  schema_version: "1.0";
  note_event_schema_version: "1.0";
  low_confidence_policy_version: "1.0";
  written_pitch_policy_version: "1.0";
  saxophone_type: SaxophoneType;
  low_confidence_threshold: number;
  confidence_interpretation: "model_signal_not_calibrated_accuracy";
  confidence_method: string;
  summary: {
    event_count: number;
    low_confidence_count: number;
  };
  events: TranscriptionReviewEvent[];
}

export interface SubmitTranscriptionInput {
  file: File;
  saxophoneType: SaxophoneType;
  inputMode: InputMode;
}

export type SubmitTranscription = (input: SubmitTranscriptionInput) => Promise<TranscriptionJob>;
export type GetTranscription = (jobId: string, signal?: AbortSignal) => Promise<TranscriptionJob>;
export type LoadTranscriptionReview = (
  jobId: string,
  signal?: AbortSignal,
) => Promise<TranscriptionReview>;

interface PublicErrorPayload {
  code: string;
  message: string;
  field: string | null;
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const SHA256_PATTERN = /^[0-9a-f]{64}$/;
const LOCAL_BACKEND_URL = "http://localhost:8080";
const TRANSCRIPTIONS_PATH = "/api/v1/transcriptions";

export class TranscriptionApiError extends Error {
  readonly code: string;
  readonly field: string | null;
  readonly status: number | null;

  constructor(code: string, message: string, field: string | null, status: number | null) {
    super(message);
    this.name = "TranscriptionApiError";
    this.code = code;
    this.field = field;
    this.status = status;
  }
}

export async function submitTranscription({
  file,
  saxophoneType,
  inputMode,
}: SubmitTranscriptionInput): Promise<TranscriptionJob> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("saxophone_type", saxophoneType);
  formData.append("input_mode", inputMode);

  let response: Response;
  try {
    response = await fetch(`${backendBaseUrl()}${TRANSCRIPTIONS_PATH}`, {
      method: "POST",
      body: formData,
    });
  } catch {
    throw unavailable();
  }

  return parseJobResponse(response, 202);
}

export async function getTranscription(
  jobId: string,
  signal?: AbortSignal,
): Promise<TranscriptionJob> {
  validateJobId(jobId);
  let response: Response;
  try {
    response = await fetch(
      `${backendBaseUrl()}${TRANSCRIPTIONS_PATH}/${encodeURIComponent(jobId)}`,
      { method: "GET", signal },
    );
  } catch (error) {
    if (signal?.aborted) {
      throw error;
    }
    throw unavailable();
  }

  const job = await parseJobResponse(response, 200);
  if (job.job_id.toLowerCase() !== jobId.toLowerCase()) {
    throw invalidResponse(response.status);
  }
  return job;
}

export async function getTranscriptionReview(
  jobId: string,
  signal?: AbortSignal,
): Promise<TranscriptionReview> {
  validateJobId(jobId);
  let response: Response;
  try {
    response = await fetch(
      `${backendBaseUrl()}${TRANSCRIPTIONS_PATH}/${encodeURIComponent(jobId)}/review`,
      { method: "GET", signal },
    );
  } catch (error) {
    if (signal?.aborted) {
      throw error;
    }
    throw unavailable();
  }

  const payload = await readJson(response);
  if (response.status !== 200) {
    if (isPublicErrorPayload(payload)) {
      throw new TranscriptionApiError(
        payload.code,
        payload.message,
        payload.field,
        response.status,
      );
    }
    throw invalidResponse(response.status);
  }
  if (!isTranscriptionReview(payload) || payload.job_id.toLowerCase() !== jobId.toLowerCase()) {
    throw invalidResponse(response.status);
  }
  return payload;
}

async function parseJobResponse(
  response: Response,
  expectedStatus: number,
): Promise<TranscriptionJob> {
  const payload = await readJson(response);
  if (response.status !== expectedStatus) {
    if (isPublicErrorPayload(payload)) {
      throw new TranscriptionApiError(
        payload.code,
        payload.message,
        payload.field,
        response.status,
      );
    }
    throw invalidResponse(response.status);
  }

  if (!isTranscriptionJob(payload)) {
    throw invalidResponse(response.status);
  }
  return payload;
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

function backendBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_SAXO_API_BASE_URL?.trim();
  return (configured || LOCAL_BACKEND_URL).replace(/\/+$/, "");
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    throw invalidResponse(response.status);
  }
}

function unavailable(): TranscriptionApiError {
  return new TranscriptionApiError(
    "BACKEND_UNAVAILABLE",
    "The Saxo service is currently unavailable. Try again.",
    null,
    null,
  );
}

function invalidResponse(status: number | null): TranscriptionApiError {
  return new TranscriptionApiError(
    "INVALID_BACKEND_RESPONSE",
    "The Saxo service returned an invalid response.",
    null,
    status,
  );
}

function isPublicErrorPayload(value: unknown): value is PublicErrorPayload {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.code === "string" &&
    value.code.length > 0 &&
    typeof value.message === "string" &&
    value.message.length > 0 &&
    (value.field === null || typeof value.field === "string")
  );
}

function isTranscriptionJob(value: unknown): value is TranscriptionJob {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.job_id === "string" &&
    UUID_PATTERN.test(value.job_id) &&
    typeof value.status === "string" &&
    value.status.trim().length > 0 &&
    typeof value.filename === "string" &&
    value.filename.trim().length > 0 &&
    !/[\\/]/.test(value.filename) &&
    isNonNegativeInteger(value.size_bytes) &&
    typeof value.audio_sha256 === "string" &&
    SHA256_PATTERN.test(value.audio_sha256) &&
    typeof value.saxophone_type === "string" &&
    SAXOPHONE_TYPES.includes(value.saxophone_type as SaxophoneType) &&
    typeof value.input_mode === "string" &&
    INPUT_MODES.includes(value.input_mode as InputMode)
  );
}

function isTranscriptionReview(value: unknown): value is TranscriptionReview {
  if (!isRecord(value) || !isRecord(value.summary) || !Array.isArray(value.events)) {
    return false;
  }
  if (
    typeof value.job_id !== "string" ||
    !UUID_PATTERN.test(value.job_id) ||
    value.schema_version !== "1.0" ||
    value.note_event_schema_version !== "1.0" ||
    value.low_confidence_policy_version !== "1.0" ||
    value.written_pitch_policy_version !== "1.0" ||
    typeof value.saxophone_type !== "string" ||
    !SAXOPHONE_TYPES.includes(value.saxophone_type as SaxophoneType) ||
    !isUnitInterval(value.low_confidence_threshold) ||
    value.confidence_interpretation !== "model_signal_not_calibrated_accuracy" ||
    typeof value.confidence_method !== "string" ||
    value.confidence_method.trim().length === 0 ||
    !isNonNegativeInteger(value.summary.event_count) ||
    !isNonNegativeInteger(value.summary.low_confidence_count) ||
    value.summary.low_confidence_count > value.summary.event_count ||
    value.summary.event_count !== value.events.length
  ) {
    return false;
  }

  let lowConfidenceCount = 0;
  for (let index = 0; index < value.events.length; index += 1) {
    const event = value.events[index];
    if (!isReviewEvent(event, index)) {
      return false;
    }
    if (event.is_low_confidence) {
      lowConfidenceCount += 1;
    }
  }
  return lowConfidenceCount === value.summary.low_confidence_count;
}

function isReviewEvent(value: unknown, expectedIndex: number): value is TranscriptionReviewEvent {
  if (!isRecord(value)) {
    return false;
  }
  return (
    value.index === expectedIndex &&
    isMidi(value.pitch_concert_midi) &&
    isMidi(value.written_pitch_midi) &&
    isFiniteNumber(value.onset_seconds) &&
    value.onset_seconds >= 0 &&
    isFiniteNumber(value.offset_seconds) &&
    value.offset_seconds > value.onset_seconds &&
    isMidi(value.velocity) &&
    isUnitInterval(value.confidence) &&
    typeof value.is_low_confidence === "boolean"
  );
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
