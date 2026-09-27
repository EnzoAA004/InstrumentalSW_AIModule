import type { TranscriptionRevisionEvent } from "./transcription-revisions";

export function maximumEventOffset(events: readonly TranscriptionRevisionEvent[]): number {
  return events.reduce((maximum, event) => Math.max(maximum, event.offset_seconds), 0);
}

export function resolveTimelineDuration(
  events: readonly TranscriptionRevisionEvent[],
  mediaDuration: number,
): number {
  if (Number.isFinite(mediaDuration) && mediaDuration > 0) {
    return mediaDuration;
  }
  return Math.max(maximumEventOffset(events), 1);
}

export function activePlaybackEventIds(
  events: readonly TranscriptionRevisionEvent[],
  currentTime: number,
): string[] {
  if (!Number.isFinite(currentTime) || currentTime < 0) {
    return [];
  }
  return events
    .filter((event) => event.onset_seconds <= currentTime && currentTime < event.offset_seconds)
    .map((event) => event.event_id);
}

export function eventsBeyondAudioDuration(
  events: readonly TranscriptionRevisionEvent[],
  mediaDuration: number,
): string[] {
  if (!Number.isFinite(mediaDuration) || mediaDuration <= 0) {
    return [];
  }
  return events
    .filter((event) => event.offset_seconds > mediaDuration)
    .map((event) => event.event_id);
}

export function formatPlaybackTime(value: number): string {
  const safeValue = Number.isFinite(value) && value > 0 ? value : 0;
  const totalMilliseconds = Math.round(safeValue * 1000);
  const minutes = Math.floor(totalMilliseconds / 60_000);
  const seconds = Math.floor((totalMilliseconds % 60_000) / 1000);
  const milliseconds = totalMilliseconds % 1000;
  return `${minutes}:${String(seconds).padStart(2, "0")}.${String(milliseconds).padStart(3, "0")}`;
}
