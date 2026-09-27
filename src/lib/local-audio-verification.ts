export type LocalAudioVerificationCode =
  | "UNSUPPORTED_AUDIO_FORMAT"
  | "EMPTY_AUDIO_FILE"
  | "AUDIO_SIZE_MISMATCH"
  | "AUDIO_HASH_MISMATCH"
  | "WEB_CRYPTO_UNAVAILABLE";

export class LocalAudioVerificationError extends Error {
  readonly code: LocalAudioVerificationCode;

  constructor(code: LocalAudioVerificationCode, message: string) {
    super(message);
    this.name = "LocalAudioVerificationError";
    this.code = code;
  }
}

export interface VerifyLocalAudioFileInput {
  file: File;
  expectedSizeBytes: number;
  expectedSha256: string;
  signal?: AbortSignal;
  cryptoProvider?: Crypto;
}

export interface VerifiedLocalAudioIdentity {
  sizeBytes: number;
  sha256: string;
}

const SUPPORTED_AUDIO_EXTENSION = /\.(mp3|wav)$/i;
const SHA256_PATTERN = /^[0-9a-f]{64}$/;

export async function verifyLocalAudioFile(
  input: VerifyLocalAudioFileInput,
): Promise<VerifiedLocalAudioIdentity> {
  const { file, expectedSizeBytes, expectedSha256, signal } = input;
  throwIfAborted(signal);

  if (!SUPPORTED_AUDIO_EXTENSION.test(file.name)) {
    throw new LocalAudioVerificationError(
      "UNSUPPORTED_AUDIO_FORMAT",
      "Only MP3 and WAV files can be selected.",
    );
  }
  if (file.size === 0) {
    throw new LocalAudioVerificationError("EMPTY_AUDIO_FILE", "The selected audio file is empty.");
  }
  if (file.size !== expectedSizeBytes) {
    throw new LocalAudioVerificationError(
      "AUDIO_SIZE_MISMATCH",
      "The selected file size does not match this transcription job.",
    );
  }

  const cryptoProvider = Object.prototype.hasOwnProperty.call(input, "cryptoProvider")
    ? input.cryptoProvider
    : globalThis.crypto;
  if (!cryptoProvider?.subtle || typeof cryptoProvider.subtle.digest !== "function") {
    throw new LocalAudioVerificationError(
      "WEB_CRYPTO_UNAVAILABLE",
      "This browser cannot verify the selected audio with Web Crypto.",
    );
  }
  if (!SHA256_PATTERN.test(expectedSha256)) {
    throw new LocalAudioVerificationError(
      "AUDIO_HASH_MISMATCH",
      "The transcription job contains an invalid audio identity.",
    );
  }

  const content = await file.arrayBuffer();
  throwIfAborted(signal);
  const sha256 = await sha256Hex(content, cryptoProvider);
  throwIfAborted(signal);

  if (sha256 !== expectedSha256) {
    throw new LocalAudioVerificationError(
      "AUDIO_HASH_MISMATCH",
      "The selected audio content does not match this transcription job.",
    );
  }
  return { sizeBytes: file.size, sha256 };
}

export async function sha256Hex(
  content: ArrayBuffer,
  cryptoProvider: Crypto = globalThis.crypto,
): Promise<string> {
  if (!cryptoProvider?.subtle || typeof cryptoProvider.subtle.digest !== "function") {
    throw new LocalAudioVerificationError(
      "WEB_CRYPTO_UNAVAILABLE",
      "This browser cannot calculate SHA-256 with Web Crypto.",
    );
  }
  const digest = await cryptoProvider.subtle.digest("SHA-256", content);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new DOMException("Audio verification was aborted.", "AbortError");
  }
}
