import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LatestRevisionArtifactDownloads } from "./latest-revision-artifact-downloads";

const JOB_ID = "11111111-1111-1111-1111-111111111111";

function history(revisionNumber = 3) {
  return {
    job_id: JOB_ID,
    latest_revision_number: revisionNumber,
    revision_count: revisionNumber + 1,
    revisions: [],
  };
}

describe("LatestRevisionArtifactDownloads", () => {
  it("loads the latest revision and renders its concrete download panel", async () => {
    const loadHistory = vi.fn().mockResolvedValue(history(3));

    render(
      <LatestRevisionArtifactDownloads
        jobId={JOB_ID}
        loadHistory={loadHistory}
        renderDownloads={(revisionNumber) => <p>Downloads for revision {revisionNumber}</p>}
      />,
    );

    expect(screen.getByText("Loading latest revision for downloads…")).toHaveAttribute(
      "aria-live",
      "polite",
    );
    expect(await screen.findByText("Downloads for revision 3")).toBeVisible();
    expect(loadHistory).toHaveBeenCalledWith(JOB_ID, expect.any(AbortSignal));
  });

  it("focuses a safe alert when revision history cannot be loaded", async () => {
    render(
      <LatestRevisionArtifactDownloads
        jobId={JOB_ID}
        loadHistory={vi.fn().mockRejectedValue(new Error("private failure"))}
        renderDownloads={() => null}
      />,
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The latest revision could not be loaded for downloads.");
    expect(alert).toHaveFocus();
    expect(alert).not.toHaveTextContent("private failure");
  });

  it("aborts and ignores a late history result after unmount", async () => {
    let resolveHistory!: (value: ReturnType<typeof history>) => void;
    const loadHistory = vi.fn().mockReturnValue(
      new Promise((resolve) => {
        resolveHistory = resolve;
      }),
    );
    const renderDownloads = vi.fn().mockReturnValue(null);
    const view = render(
      <LatestRevisionArtifactDownloads
        jobId={JOB_ID}
        loadHistory={loadHistory}
        renderDownloads={renderDownloads}
      />,
    );
    await waitFor(() => expect(loadHistory).toHaveBeenCalled());
    const signal = loadHistory.mock.calls[0]?.[1] as AbortSignal;

    view.unmount();
    resolveHistory(history(4));
    await Promise.resolve();

    expect(signal.aborted).toBe(true);
    expect(renderDownloads).not.toHaveBeenCalled();
  });
});
