import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { TranscriptionReview } from "@/lib/transcription-api";
import type {
  TranscriptionRevision,
  TranscriptionRevisionHistory,
} from "@/lib/transcription-revisions";
import { TranscriptionReviewView } from "./transcription-review";
import { TranscriptionRevisionEditor } from "./transcription-revision-editor";

const JOB_ID = "11111111-1111-1111-1111-111111111111";
const REVIEW: TranscriptionReview = {
  job_id: JOB_ID,
  schema_version: "1.0",
  note_event_schema_version: "1.0",
  low_confidence_policy_version: "1.0",
  written_pitch_policy_version: "1.0",
  saxophone_type: "alto",
  low_confidence_threshold: 0.5,
  confidence_interpretation: "model_signal_not_calibrated_accuracy",
  confidence_method: "model_probability",
  summary: { event_count: 1, low_confidence_count: 0 },
  events: [
    {
      index: 0,
      pitch_concert_midi: 60,
      written_pitch_midi: 69,
      onset_seconds: 0,
      offset_seconds: 1,
      velocity: 90,
      confidence: 0.8,
      is_low_confidence: false,
    },
  ],
};
const HISTORY: TranscriptionRevisionHistory = {
  job_id: JOB_ID,
  latest_revision_number: 0,
  revision_count: 1,
  revisions: [
    {
      revision_number: 0,
      parent_revision_number: null,
      created_at: "2026-07-22T12:00:00Z",
      event_count: 1,
      model_event_count: 1,
      human_event_count: 0,
      derived_artifacts_status: "CURRENT",
    },
  ],
};
const REVISION: TranscriptionRevision = {
  job_id: JOB_ID,
  revision_number: 0,
  parent_revision_number: null,
  created_at: "2026-07-22T12:00:00Z",
  saxophone_type: "alto",
  schema_version: "1.0",
  derived_artifacts_status: "CURRENT",
  summary: { event_count: 1, model_event_count: 1, human_event_count: 0 },
  events: [
    {
      event_id: "source-0",
      origin: "model",
      source_index: 0,
      pitch_concert_midi: 60,
      written_pitch_midi: 69,
      onset_seconds: 0,
      offset_seconds: 1,
      velocity: 90,
      confidence: 0.8,
      is_low_confidence: false,
    },
  ],
};

describe("SAX-044 navigation", () => {
  it("links from the read-only review to synchronized playback", async () => {
    render(<TranscriptionReviewView jobId={JOB_ID} load={vi.fn().mockResolvedValue(REVIEW)} />);
    expect(await screen.findByRole("link", { name: "Play synchronized review" })).toHaveAttribute(
      "href",
      `/transcriptions/${JOB_ID}/review/playback`,
    );
  });

  it("links from the revision editor to synchronized playback", async () => {
    render(
      <TranscriptionRevisionEditor
        jobId={JOB_ID}
        loadHistory={vi.fn().mockResolvedValue(HISTORY)}
        loadRevision={vi.fn().mockResolvedValue(REVISION)}
      />,
    );
    expect(await screen.findByRole("link", { name: "Play synchronized review" })).toHaveAttribute(
      "href",
      `/transcriptions/${JOB_ID}/review/playback`,
    );
  });
});
