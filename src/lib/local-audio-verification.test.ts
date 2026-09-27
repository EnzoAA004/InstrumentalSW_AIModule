import { webcrypto } from "node:crypto";

import { describe, expect, it, vi } from "vitest";

import {
  LocalAudioVerificationError,
  sha256Hex,
  verifyLocalAudioFile,
} from "./local-audio-verification";

const ABC_SHA256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";

function syntheticFile(name: string, bytes: Uint8Array = new TextEncoder().encode("abc")): File {
  return new File([bytes], name, {
    type: name.toLowerCase().endsWith(".mp3") ? "audio/mpeg" : "audio/wav",
  });
}

function exactArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  const buffer = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(buffer).set(bytes);
  return buffer;
}

function digestProvider(hex = ABC_SHA256): Crypto {
  const bytes = Uint8Array.from(hex.match(/.{2}/g) ?? [], (part) => Number.parseInt(part, 16));
  return {
    subtle: {
      digest: vi.fn().mockResolvedValue(exactArrayBuffer(bytes)),
    },
  } as unknown as Crypto;
}

async function expectCode(promise: Promise<unknown>, code: string): Promise<void> {
  await expect(promise).rejects.toMatchObject({ code });
}

describe("sha256Hex", () => {
  it("calculates the known lowercase SHA-256 for synthetic bytes", async () => {
    const bytes = new TextEncoder().encode("abc");
    await expect(sha256Hex(exactArrayBuffer(bytes), webcrypto as unknown as Crypto)).resolves.toBe(
      ABC_SHA256,
    );
  });
});

describe("verifyLocalAudioFile", () => {
  it.each(["take.mp3", "take.wav", "TAKE.MP3", "TAKE.WAV"])(
    "accepts supported case-insensitive extension %s",
    async (name) => {
      const file = syntheticFile(name);
      await expect(
        verifyLocalAudioFile({
          file,
          expectedSizeBytes: file.size,
          expectedSha256: ABC_SHA256,
          cryptoProvider: digestProvider(),
        }),
      ).resolves.toEqual({ sizeBytes: file.size, sha256: ABC_SHA256 });
    },
  );

  it("accepts a renamed file when bytes and size match", async () => {
    const file = syntheticFile("renamed-original.wav");
    await expect(
      verifyLocalAudioFile({
        file,
        expectedSizeBytes: file.size,
        expectedSha256: ABC_SHA256,
        cryptoProvider: digestProvider(),
      }),
    ).resolves.toMatchObject({ sha256: ABC_SHA256 });
  });

  it("rejects unsupported and empty files before hashing", async () => {
    const cryptoProvider = digestProvider();
    await expectCode(
      verifyLocalAudioFile({
        file: syntheticFile("take.txt"),
        expectedSizeBytes: 3,
        expectedSha256: ABC_SHA256,
        cryptoProvider,
      }),
      "UNSUPPORTED_AUDIO_FORMAT",
    );
    await expectCode(
      verifyLocalAudioFile({
        file: syntheticFile("empty.wav", new Uint8Array()),
        expectedSizeBytes: 0,
        expectedSha256: ABC_SHA256,
        cryptoProvider,
      }),
      "EMPTY_AUDIO_FILE",
    );
    expect(cryptoProvider.subtle.digest).not.toHaveBeenCalled();
  });

  it("checks size before reading bytes or hashing", async () => {
    const file = syntheticFile("take.wav");
    const arrayBuffer = vi.spyOn(file, "arrayBuffer");
    const cryptoProvider = digestProvider();

    await expectCode(
      verifyLocalAudioFile({
        file,
        expectedSizeBytes: file.size + 1,
        expectedSha256: ABC_SHA256,
        cryptoProvider,
      }),
      "AUDIO_SIZE_MISMATCH",
    );

    expect(arrayBuffer).not.toHaveBeenCalled();
    expect(cryptoProvider.subtle.digest).not.toHaveBeenCalled();
  });

  it("rejects same filename and size when the content hash differs", async () => {
    const file = syntheticFile("take.wav");
    await expectCode(
      verifyLocalAudioFile({
        file,
        expectedSizeBytes: file.size,
        expectedSha256: "0".repeat(64),
        cryptoProvider: digestProvider(),
      }),
      "AUDIO_HASH_MISMATCH",
    );
  });

  it("fails safely when Web Crypto is unavailable", async () => {
    const file = syntheticFile("take.wav");
    await expectCode(
      verifyLocalAudioFile({
        file,
        expectedSizeBytes: file.size,
        expectedSha256: ABC_SHA256,
        cryptoProvider: undefined,
      }),
      "WEB_CRYPTO_UNAVAILABLE",
    );
  });

  it("honors abort before and after the digest completes", async () => {
    const file = syntheticFile("take.wav");
    const before = new AbortController();
    before.abort();
    await expect(
      verifyLocalAudioFile({
        file,
        expectedSizeBytes: file.size,
        expectedSha256: ABC_SHA256,
        cryptoProvider: digestProvider(),
        signal: before.signal,
      }),
    ).rejects.toMatchObject({ name: "AbortError" });

    let resolveDigest!: (value: ArrayBuffer) => void;
    const digest = vi.fn().mockReturnValue(
      new Promise<ArrayBuffer>((resolve) => {
        resolveDigest = resolve;
      }),
    );
    const during = new AbortController();
    const promise = verifyLocalAudioFile({
      file,
      expectedSizeBytes: file.size,
      expectedSha256: ABC_SHA256,
      cryptoProvider: { subtle: { digest } } as unknown as Crypto,
      signal: during.signal,
    });
    await Promise.resolve();
    during.abort();
    resolveDigest(
      exactArrayBuffer(
        Uint8Array.from(ABC_SHA256.match(/.{2}/g) ?? [], (part) => Number.parseInt(part, 16)),
      ),
    );
    await expect(promise).rejects.toMatchObject({ name: "AbortError" });
  });

  it("does not send bytes, create FormData, or log file/hash content", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const formData = vi.fn();
    const originalFormData = globalThis.FormData;
    vi.stubGlobal("FormData", formData);
    const consoleLog = vi.spyOn(console, "log").mockImplementation(() => undefined);
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const file = syntheticFile("take.wav");

    await verifyLocalAudioFile({
      file,
      expectedSizeBytes: file.size,
      expectedSha256: ABC_SHA256,
      cryptoProvider: digestProvider(),
    });

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(formData).not.toHaveBeenCalled();
    expect(consoleLog).not.toHaveBeenCalled();
    expect(consoleError).not.toHaveBeenCalled();
    vi.stubGlobal("FormData", originalFormData);
  });

  it("exposes stable controlled verification errors", () => {
    expect(new LocalAudioVerificationError("AUDIO_HASH_MISMATCH", "message")).toMatchObject({
      name: "LocalAudioVerificationError",
      code: "AUDIO_HASH_MISMATCH",
    });
  });
});
