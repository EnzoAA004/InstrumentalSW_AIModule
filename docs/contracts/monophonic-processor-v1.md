# Monophonic audio-to-score processor — v1

## Objective

SAX-036 implements the concrete `TranscriptionJobProcessor` consumed by the durable SAX-072 worker for the first MVP scope: one isolated monophonic saxophone recording.

The processor is orchestration only. Existing domain/application components remain the owners of validation, note-event filtering, confidence, transposition, tempo, quantization and export rules.

## Pipeline

```text
TranscriptionJob + original bytes
  ↓
CanonicalAudioConverter
  ↓
TranscriptionEngine
  ↓
PostProcessTranscriptionEvents
  ↓
MarkLowConfidenceEvents
  ↓
TransposeWrittenPitchEvents
  ↓
EstimateTranscriptionTempo
  └─ insufficient onsets → configurable manual fallback
  ↓
QuantizeMonophonicRhythm
  ├─ ExportWrittenPitchToMidi
  └─ ExportQuantizedRhythmToMusicXml
       ↓
       RenderMusicXmlToSvg
  ↓
RegisterTranscriptionReview (revision 0)
  ↓
RegisterRevisionArtifacts
```

## Audio validation and worker failure policy

The processor builds the trusted `OriginalAudioReference` from persisted job metadata and sends the private source bytes through the configured canonical converter.

Two deterministic source failures are terminal:

- undecodable content → `AUDIO_CONTENT_INVALID`;
- duration above the configured limit → `AUDIO_DURATION_LIMIT_EXCEEDED`.

They become `TerminalProcessingError` values. The worker acknowledges the current queue claim and stores the specific failure code without retrying.

Other unexpected exceptions continue through the SAX-072 bounded retry path because they may represent transient runtime, model, storage or infrastructure failures.

The queue attempt token remains authoritative: even a terminal processor error changes job state only if the worker still owns the claim.

## Tempo fallback

Automatic onset-interval estimation is attempted first.

A valid short phrase may contain too few unique onsets for a statistically meaningful estimate. `TempoEstimationUnavailableError` therefore does not fail the whole transcription. The processor resolves tempo manually using a configurable fallback, defaulting to 120 BPM.

Other tempo errors are not silently converted to the fallback.

## Revision-zero output

The successful processor registers the written-pitch review first, which initializes immutable revision zero, then registers one artifact bundle for that revision.

Stable artifact identifiers are:

- `midi`;
- `musicxml`;
- `svg-page-001`, `svg-page-002`, ... when rendered.

Filenames are deterministic:

- `transcription-r0.mid`;
- `transcription-r0.musicxml`;
- `transcription-r0-page-001.svg`, etc.

## Degraded score rendering

A controlled score-rendering failure does not invalidate already-valid MIDI or MusicXML. In that case revision zero is registered with the review plus a two-artifact bundle containing MIDI and MusicXML only.

Unexpected programming errors are not swallowed.

## Diagnostics

The processor may receive an optional diagnostics observer for integration and operational visibility. The observer records stage counts and artifact sizes after a successful run, including canonical audio bytes, raw baseline events, post-processed events, confidence annotations, written-pitch events, tempo, quantized notes/timeline items, MIDI bytes, MusicXML bytes and SVG page count.

Diagnostics are read-only. They do not change validation, retries, review registration, artifact registration, or public API behavior.

## Real integration coverage

The baseline integration test and full processor E2E share a generated, license-safe saxophone-like WAV fixture from `tests/synthetic_audio.py` and execute the real chain with:

- FFmpeg canonical conversion;
- pinned FiloSax baseline when the baseline extra is installed;
- deterministic post-processing/transposition/tempo/quantization;
- Mido MIDI encoding;
- standard-library MusicXML encoding;
- Verovio MusicXML validation;
- Verovio SVG rendering.

Python 3.11 CI requires the real pinned baseline. Other supported Python jobs retain the existing optional-baseline skip policy.

The final SAX-036 Quality run validated the real pinned-baseline E2E path in Python 3.11 and reached revision zero with MIDI, MusicXML and SVG artifacts.

## Deferred

SAX-036 does not add:

- source separation or mixture processing;
- a multiinstrument pipeline;
- a long-running worker CLI/service composition;
- authentication;
- review/revision database persistence;
- retention/reconciliation;
- model fine-tuning.
