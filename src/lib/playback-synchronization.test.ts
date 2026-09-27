import { describe, expect, it } from "vitest";

import type { TranscriptionRevisionEvent } from "./transcription-revisions";
import {
  activePlaybackEventIds,
  eventsBeyondAudioDuration,
  formatPlaybackTime,
  maximumEventOffset,
  resolveTimelineDuration,
} from "./playback-synchronization";

const EVENTS: TranscriptionRevisionEvent[] = [
  {
    event_id: "source-0",
    origin: "model",
    source_index: 0,
    pitch_concert_midi: 60,
    written_pitch_midi: 69,
    onset_seconds: 0,
    offset_seconds: 1,
    velocity: 90,
    confidence: 0.42,
    is_low_confidence: true,
  },
  {
    event_id: "human-1",
    origin: "human",
    source_index: null,
    pitch_concert_midi: 64,
    written_pitch_midi: 73,
    onset_seconds: 0.5,
    offset_seconds: 1.5,
    velocity: 64,
    confidence: null,
    is_low_confidence: null,
  },
  {
    event_id: "source-2",
    origin: "model",
    source_index: 2,
    pitch_concert_midi: 67,
    written_pitch_midi: 76,
    onset_seconds: 2,
    offset_seconds: 4,
    velocity: 100,
    confidence: 0.82,
    is_low_confidence: false,
  },
];

describe("playback synchronization helpers", () => {
  it("uses maximum event offset before media metadata and real media duration after metadata", () => {
    expect(maximumEventOffset(EVENTS)).toBe(4);
    expect(resolveTimelineDuration(EVENTS, Number.NaN)).toBe(4);
    expect(resolveTimelineDuration(EVENTS, 0)).toBe(4);
    expect(resolveTimelineDuration(EVENTS, 3.25)).toBe(3.25);
    expect(resolveTimelineDuration([], Number.NaN)).toBe(1);
  });

  it("marks exact onset inclusive and exact offset exclusive", () => {
    expect(activePlaybackEventIds(EVENTS, -1)).toEqual([]);
    expect(activePlaybackEventIds(EVENTS, 0)).toEqual(["source-0"]);
    expect(activePlaybackEventIds(EVENTS, 0.5)).toEqual(["source-0", "human-1"]);
    expect(activePlaybackEventIds(EVENTS, 1)).toEqual(["human-1"]);
    expect(activePlaybackEventIds(EVENTS, 1.5)).toEqual([]);
    expect(activePlaybackEventIds(EVENTS, 2)).toEqual(["source-2"]);
    expect(activePlaybackEventIds(EVENTS, 4)).toEqual([]);
  });

  it("preserves API order while returning every overlapping active event", () => {
    const reversed = [EVENTS[1], EVENTS[0], EVENTS[2]];
    expect(activePlaybackEventIds(reversed, 0.75)).toEqual(["human-1", "source-0"]);
    expect(reversed).toEqual([EVENTS[1], EVENTS[0], EVENTS[2]]);
  });

  it("reports events beyond real media duration without truncating source values", () => {
    expect(eventsBeyondAudioDuration(EVENTS, 3)).toEqual(["source-2"]);
    expect(EVENTS[2]).toMatchObject({ onset_seconds: 2, offset_seconds: 4 });
    expect(eventsBeyondAudioDuration(EVENTS, Number.NaN)).toEqual([]);
  });

  it("formats current time text deterministically", () => {
    expect(formatPlaybackTime(0)).toBe("0:00.000");
    expect(formatPlaybackTime(65.25)).toBe("1:05.250");
    expect(formatPlaybackTime(Number.NaN)).toBe("0:00.000");
  });

  it("does not invent confidence for human events or alter model confidence", () => {
    expect(EVENTS[0].confidence).toBe(0.42);
    expect(EVENTS[1].confidence).toBeNull();
    expect(EVENTS[1].is_low_confidence).toBeNull();
  });
});
