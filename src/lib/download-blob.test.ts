import { afterEach, describe, expect, it, vi } from "vitest";

import { saveVerifiedArtifactBlob } from "./download-blob";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("saveVerifiedArtifactBlob", () => {
  it("creates one temporary link, clicks, removes, and revokes its object URL", () => {
    const append = vi.spyOn(document.body, "appendChild");
    const createObjectURL = vi.fn().mockReturnValue("blob:artifact-1");
    const revokeObjectURL = vi.fn();
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    const blob = new Blob([new Uint8Array([1, 2, 3])], { type: "audio/midi" });

    saveVerifiedArtifactBlob(blob, "transcription-r2.mid", { createObjectURL, revokeObjectURL });

    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    const link = append.mock.calls.at(-1)?.[0] as HTMLAnchorElement;
    expect(link.download).toBe("transcription-r2.mid");
    expect(link.href).toContain("blob:artifact-1");
    expect(document.body.contains(link)).toBe(false);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:artifact-1");
  });

  it("revokes and removes the link when clicking throws", () => {
    const revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {
      throw new Error("blocked");
    });

    expect(() =>
      saveVerifiedArtifactBlob(new Blob(["x"]), "safe.svg", {
        createObjectURL: vi.fn().mockReturnValue("blob:artifact-2"),
        revokeObjectURL,
      }),
    ).toThrow("blocked");
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:artifact-2");
    expect(document.querySelector('a[href="blob:artifact-2"]')).toBeNull();
  });
});
