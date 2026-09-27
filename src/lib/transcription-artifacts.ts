export type RevisionArtifactType = "midi" | "musicxml" | "svg";

export interface RevisionArtifactDescriptor {
  artifact_id: string;
  artifact_type: RevisionArtifactType;
  filename: string;
  media_type: string;
  extension: string;
  size_bytes: number;
  sha256: string;
  order: number;
}

export interface RevisionArtifactList {
  job_id: string;
  revision_number: number;
  artifacts: RevisionArtifactDescriptor[];
}

export interface DownloadedRevisionArtifact {
  blob: Blob;
  filename: string;
  mediaType: string;
  sizeBytes: number;
  sha256: string;
}

interface PublicErrorPayload {
  code: string;
  message: string;
  field: string | null;
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ID_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const FILENAME_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;
const SHA_PATTERN = /^[0-9a-f]{64}$/;
const LOCAL_BACKEND_URL = "http://localhost:8080";
const EXPECTED: Record<RevisionArtifactType, { mediaType: string; extension: string }> = {
  midi: { mediaType: "audio/midi", extension: ".mid" },
  musicxml: {
    mediaType: "application/vnd.recordare.musicxml+xml",
    extension: ".musicxml",
  },
  svg: { mediaType: "image/svg+xml", extension: ".svg" },
};

export class TranscriptionArtifactError extends Error {
  readonly code: string;
  readonly field: string | null;
  readonly status: number | null;

  constructor(code: string, message: string, field: string | null, status: number | null) {
    super(message);
    this.name = "TranscriptionArtifactError";
    this.code = code;
    this.field = field;
    this.status = status;
  }
}

export async function getRevisionArtifacts(
  jobId: string,
  revisionNumber: number,
  signal?: AbortSignal,
): Promise<RevisionArtifactList> {
  validateIdentity(jobId, revisionNumber);
  const response = await safeFetch(
    artifactBaseUrl(jobId, revisionNumber),
    { method: "GET", signal },
    signal,
  );
  const payload = await readJson(response);
  throwPublicError(response, payload);
  if (!isRevisionArtifactList(payload, jobId, revisionNumber)) {
    throw invalidResponse(response.status);
  }
  return payload;
}

export async function downloadRevisionArtifact(
  jobId: string,
  revisionNumber: number,
  artifactId: string,
  signal?: AbortSignal,
  cryptoProvider: Crypto | undefined = globalThis.crypto,
): Promise<DownloadedRevisionArtifact> {
  validateIdentity(jobId, revisionNumber);
  if (!ID_PATTERN.test(artifactId)) throw invalidResponse(null);
  const listing = await getRevisionArtifacts(jobId, revisionNumber, signal);
  const descriptor = listing.artifacts.find((value) => value.artifact_id === artifactId);
  if (descriptor === undefined) {
    throw new TranscriptionArtifactError(
      "ARTIFACT_NOT_FOUND",
      "Revision artifact not found.",
      "artifact_id",
      404,
    );
  }
  const response = await safeFetch(
    `${artifactBaseUrl(jobId, revisionNumber)}/${encodeURIComponent(artifactId)}`,
    { method: "GET", signal },
    signal,
  );
  if (response.status !== 200) {
    const payload = await readJson(response);
    throwPublicError(response, payload);
    throw invalidResponse(response.status);
  }
  validateDownloadHeaders(response, descriptor);
  const bytes = await response.arrayBuffer();
  if (bytes.byteLength !== descriptor.size_bytes) throw invalidResponse(response.status);
  if (!cryptoProvider?.subtle || typeof cryptoProvider.subtle.digest !== "function") {
    throw new TranscriptionArtifactError(
      "WEB_CRYPTO_UNAVAILABLE",
      "This browser cannot verify the downloaded artifact.",
      null,
      null,
    );
  }
  const digest = await cryptoProvider.subtle.digest("SHA-256", bytes);
  const calculated = Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
  if (calculated !== descriptor.sha256) throw invalidResponse(response.status);
  return {
    blob: new Blob([bytes], { type: descriptor.media_type }),
    filename: descriptor.filename,
    mediaType: descriptor.media_type,
    sizeBytes: descriptor.size_bytes,
    sha256: descriptor.sha256,
  };
}

function validateDownloadHeaders(response: Response, descriptor: RevisionArtifactDescriptor): void {
  if (response.headers.get("Content-Type") !== descriptor.media_type)
    throw invalidResponse(response.status);
  if (
    response.headers.get("Content-Disposition") !== `attachment; filename="${descriptor.filename}"`
  ) {
    throw invalidResponse(response.status);
  }
  const length = response.headers.get("Content-Length");
  if (length !== null && Number(length) !== descriptor.size_bytes)
    throw invalidResponse(response.status);
  if (response.headers.get("X-Content-SHA256") !== descriptor.sha256)
    throw invalidResponse(response.status);
}

function isRevisionArtifactList(
  value: unknown,
  jobId: string,
  revisionNumber: number,
): value is RevisionArtifactList {
  if (!isRecord(value) || !Array.isArray(value.artifacts)) return false;
  if (
    Object.keys(value).sort().join(",") !== "artifacts,job_id,revision_number" ||
    typeof value.job_id !== "string" ||
    value.job_id.toLowerCase() !== jobId.toLowerCase() ||
    value.revision_number !== revisionNumber ||
    value.artifacts.length === 0
  ) {
    return false;
  }
  const ids = new Set<string>();
  const filenames = new Set<string>();
  return value.artifacts.every((artifact, index) => {
    if (!isDescriptor(artifact, index)) return false;
    if (ids.has(artifact.artifact_id) || filenames.has(artifact.filename)) return false;
    ids.add(artifact.artifact_id);
    filenames.add(artifact.filename);
    return true;
  });
}

function isDescriptor(value: unknown, order: number): value is RevisionArtifactDescriptor {
  if (!isRecord(value)) return false;
  const fields = [
    "artifact_id",
    "artifact_type",
    "extension",
    "filename",
    "media_type",
    "order",
    "sha256",
    "size_bytes",
  ];
  if (Object.keys(value).sort().join(",") !== fields.sort().join(",")) return false;
  if (
    typeof value.artifact_id !== "string" ||
    !ID_PATTERN.test(value.artifact_id) ||
    !isArtifactType(value.artifact_type) ||
    typeof value.filename !== "string" ||
    !safeFilename(value.filename) ||
    typeof value.media_type !== "string" ||
    typeof value.extension !== "string" ||
    !Number.isSafeInteger(value.size_bytes) ||
    typeof value.size_bytes !== "number" ||
    value.size_bytes <= 0 ||
    typeof value.sha256 !== "string" ||
    !SHA_PATTERN.test(value.sha256) ||
    value.order !== order
  ) {
    return false;
  }
  const expected = EXPECTED[value.artifact_type];
  return (
    value.media_type === expected.mediaType &&
    value.extension === expected.extension &&
    value.filename.endsWith(expected.extension)
  );
}

function isArtifactType(value: unknown): value is RevisionArtifactType {
  return value === "midi" || value === "musicxml" || value === "svg";
}

function safeFilename(value: string): boolean {
  return (
    FILENAME_PATTERN.test(value) &&
    !value.startsWith(".") &&
    !value.includes("..") &&
    !value.includes("/") &&
    !value.includes("\\") &&
    !value.includes("\r") &&
    !value.includes("\n")
  );
}

function validateIdentity(jobId: string, revisionNumber: number): void {
  if (!UUID_PATTERN.test(jobId)) {
    throw new TranscriptionArtifactError(
      "INVALID_JOB_ID",
      "Job ID must be a valid UUID.",
      "job_id",
      400,
    );
  }
  if (!Number.isSafeInteger(revisionNumber) || revisionNumber < 0) {
    throw new TranscriptionArtifactError(
      "REVISION_NOT_FOUND",
      "Transcription revision not found.",
      "revision_number",
      404,
    );
  }
}

function artifactBaseUrl(jobId: string, revisionNumber: number): string {
  return `${backendBaseUrl()}/api/v1/transcriptions/${encodeURIComponent(jobId)}/revisions/${revisionNumber}/artifacts`;
}

function backendBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_SAXO_API_BASE_URL?.trim() || LOCAL_BACKEND_URL).replace(
    /\/+$/,
    "",
  );
}

async function safeFetch(url: string, init: RequestInit, signal?: AbortSignal): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new TranscriptionArtifactError(
      "BACKEND_UNAVAILABLE",
      "The Saxo service is currently unavailable. Try again.",
      null,
      null,
    );
  }
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    throw invalidResponse(response.status);
  }
}

function throwPublicError(response: Response, payload: unknown): void {
  if (response.status === 200) return;
  if (isPublicErrorPayload(payload)) {
    throw new TranscriptionArtifactError(
      payload.code,
      payload.message,
      payload.field,
      response.status,
    );
  }
  throw invalidResponse(response.status);
}

function isPublicErrorPayload(value: unknown): value is PublicErrorPayload {
  return (
    isRecord(value) &&
    typeof value.code === "string" &&
    value.code.length > 0 &&
    typeof value.message === "string" &&
    value.message.length > 0 &&
    (value.field === null || typeof value.field === "string")
  );
}

function invalidResponse(status: number | null): TranscriptionArtifactError {
  return new TranscriptionArtifactError(
    "INVALID_BACKEND_RESPONSE",
    "The Saxo service returned an invalid artifact response.",
    null,
    status,
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
