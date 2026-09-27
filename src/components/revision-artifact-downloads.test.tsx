import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RevisionArtifactDownloads } from "./revision-artifact-downloads";
import {
  TranscriptionArtifactError,
  type RevisionArtifactList,
} from "@/lib/transcription-artifacts";

const JOB_ID = "11111111-1111-1111-1111-111111111111";
const SHA = "9f64a747e1b97f131fabb6b447296c9b6f0201e79fb3c5356e6c77e89b6a806a";

function list(): RevisionArtifactList {
  return {
    job_id: JOB_ID,
    revision_number: 2,
    artifacts: [
      {
        artifact_id: "midi",
        artifact_type: "midi",
        filename: "transcription-r2.mid",
        media_type: "audio/midi",
        extension: ".mid",
        size_bytes: 4,
        sha256: SHA,
        order: 0,
      },
      {
        artifact_id: "musicxml",
        artifact_type: "musicxml",
        filename: "transcription-r2.musicxml",
        media_type: "application/vnd.recordare.musicxml+xml",
        extension: ".musicxml",
        size_bytes: 12,
        sha256: "a".repeat(64),
        order: 1,
      },
      {
        artifact_id: "svg-page-001",
        artifact_type: "svg",
        filename: "transcription-r2-page-001.svg",
        media_type: "image/svg+xml",
        extension: ".svg",
        size_bytes: 20,
        sha256: "b".repeat(64),
        order: 2,
      },
      {
        artifact_id: "svg-page-002",
        artifact_type: "svg",
        filename: "transcription-r2-page-002.svg",
        media_type: "image/svg+xml",
        extension: ".svg",
        size_bytes: 21,
        sha256: "c".repeat(64),
        order: 3,
      },
    ],
  };
}

describe("RevisionArtifactDownloads", () => {
  it("renders available MIDI, MusicXML and SVG descriptors without PDF", async () => {
    render(
      <RevisionArtifactDownloads
        jobId={JOB_ID}
        revisionNumber={2}
        loadArtifacts={vi.fn().mockResolvedValue(list())}
      />,
    );

    expect(screen.getByText("Loading revision artifacts…")).toHaveAttribute("aria-live", "polite");
    expect(
      await screen.findByRole("heading", { name: "Revision artifact downloads" }),
    ).toBeVisible();
    expect(screen.getByText("MIDI")).toBeVisible();
    expect(screen.getByText("MusicXML")).toBeVisible();
    expect(screen.getAllByText("SVG")).toHaveLength(2);
    expect(screen.queryByText(/PDF/i)).not.toBeInTheDocument();
    expect(screen.getByText(SHA)).toBeVisible();
    expect(screen.getByText("9f64a747e1b9…")).toBeVisible();
    expect(screen.getByText("Downloads are retrieved through the Saxo product API.")).toBeVisible();
    expect(screen.getByText("No public storage URL is exposed.")).toBeVisible();
  });

  it("shows the honest not-ready state without false buttons", async () => {
    render(
      <RevisionArtifactDownloads
        jobId={JOB_ID}
        revisionNumber={2}
        loadArtifacts={vi
          .fn()
          .mockRejectedValue(
            new TranscriptionArtifactError(
              "ARTIFACTS_NOT_READY",
              "Artifacts are not available for this revision yet.",
              "revision_number",
              409,
            ),
          )}
      />,
    );

    expect(
      await screen.findByText("Artifacts are not available for this revision yet."),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: /Download/ })).not.toBeInTheDocument();
  });

  it("communicates downloading and success while preserving focus", async () => {
    const user = userEvent.setup();
    let resolveDownload!: (value: {
      blob: Blob;
      filename: string;
      mediaType: string;
      sizeBytes: number;
      sha256: string;
    }) => void;
    const download = vi.fn().mockReturnValue(
      new Promise((resolve) => {
        resolveDownload = resolve;
      }),
    );
    render(
      <RevisionArtifactDownloads
        jobId={JOB_ID}
        revisionNumber={2}
        loadArtifacts={vi.fn().mockResolvedValue(list())}
        downloadArtifact={download}
        saveBlob={vi.fn()}
      />,
    );
    const button = await screen.findByRole("button", {
      name: "Download MIDI transcription-r2.mid",
    });

    await user.click(button);
    expect(button).toBeDisabled();
    expect(screen.getByText("Downloading transcription-r2.mid…")).toHaveAttribute(
      "aria-live",
      "polite",
    );
    resolveDownload({
      blob: new Blob([new Uint8Array([1, 2, 3, 4])], { type: "audio/midi" }),
      filename: "transcription-r2.mid",
      mediaType: "audio/midi",
      sizeBytes: 4,
      sha256: SHA,
    });
    await waitFor(() => expect(screen.getByText("Downloaded transcription-r2.mid.")).toBeVisible());
    expect(button).toHaveFocus();
  });

  it("focuses controlled download errors", async () => {
    const user = userEvent.setup();
    render(
      <RevisionArtifactDownloads
        jobId={JOB_ID}
        revisionNumber={2}
        loadArtifacts={vi.fn().mockResolvedValue(list())}
        downloadArtifact={vi.fn().mockRejectedValue(new Error("failure"))}
      />,
    );
    await user.click(
      await screen.findByRole("button", { name: "Download MIDI transcription-r2.mid" }),
    );
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveFocus();
    expect(alert).toHaveTextContent("The artifact could not be downloaded safely.");
  });
});
