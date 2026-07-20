# HF saxophone transcription baseline — v1

## Purpose

SAX-021 introduces the first real audio-to-note baseline for isolated saxophone while keeping the application independent from a concrete model. Canonical 16 kHz mono PCM audio is converted into `NoteEventBatch` schema `1.0` through the application-level `TranscriptionEngine` port.

The capability is internal. It is not connected to FastAPI, job state, permanent MIDI, or persistent storage.

## Why this baseline

The selected checkpoint is specifically trained for saxophone, so it is a more relevant first baseline for the saxophone-focused MVP than a generic multi-instrument checkpoint. The adapter remains replaceable behind the common application port, allowing later comparison without changing the use case or `NoteEvent` consumers.

## Pinned identity

```text
package:            hf-midi-transcription
reported version:   0.1.1
source commit:      96f6797881e9497cbfc8f8e5deccea9c1f2f7adc
model ID:           xavriley/midi-transcription-models
model revision:     982ce108d7010bc3c4f36cf851caea8d4c94763d
checkpoint:         filosax_25k.pth
checkpoint size:    99341469 bytes
checkpoint SHA-256: 448cf2c8ea6d4b77f7435f5b9a496211ea60300c5c17fa9c754da764f75f3a6a
sample rate:        16000 Hz
device:             CPU
```

Version `0.1.1` is installed from the fixed official source commit because no usable PyPI distribution exists for this integration. The installed distribution reports version `0.1.1`; neither the package source nor the model revision follows a floating branch.

## Declared license

The upstream package and model metadata declare the MIT license. This records the upstream declaration and is not a legal conclusion about every transitive dependency or dataset used to train the checkpoint.

## Optional installation

Core development remains:

```bash
python -m pip install -e ".[dev]"
```

The validated baseline environment is Python 3.11:

```bash
python -m pip install -e ".[dev,baseline]"
```

The model is not downloaded while the project is installed. Hugging Face resolves it only when inference or the real baseline integration test runs. A first execution downloads the checkpoint into the Hugging Face cache; later executions may obtain a cache hit, but size and SHA-256 verification are repeated before loading.

Python 3.12 and 3.13 remain supported for the Saxo core. Their real baseline test is skipped with an explicit compatibility reason because the optional dependency is constrained to Python 3.11.

The optional stack includes PyTorch and its transitive numerical/audio dependencies. Its installation is significantly larger and slower than the core development environment; this is why it is isolated in the `baseline` extra and required only in the Python 3.11 CI job.

## Adapter architecture

```text
BinaryStream
    │
    ▼
TranscribeCanonicalAudio
    │ depends on
    ▼
TranscriptionEngine (Protocol)
    │ implemented by
    ▼
HfSaxophoneTranscriptionEngine
    ├── PinnedFiloSaxCheckpointResolver
    ├── HfMidiRuntimeFactory
    ├── convert_baseline_output
    └── TemporaryDirectory
             │
             ▼
TranscriptionResult
    ├── NoteEventBatch 1.0
    ├── TranscriptionModelIdentity
    └── TranscriptionSettings
```

Domain and application modules do not import FastAPI, Hugging Face, PyTorch, or `hf_midi_transcription`. Download, runtime initialization, inference, and normalization remain infrastructure concerns.

## Input and temporary files

The adapter accepts a non-seekable `BinaryStream` requiring only:

```python
read(size: int) -> bytes
```

It does not require `seek`, `tell`, `fileno`, a filename, a local path, FastAPI types, or a complete in-memory byte object. The stream is copied in bounded 64 KiB blocks into `canonical.wav` inside a context-managed temporary workspace.

The expected canonical representation is WAV PCM16, mono, 16000 Hz. The external runtime also requires a MIDI output path, so the workspace contains an internal `baseline.mid`. That MIDI is temporary and is not the source of the returned contract: raw events and activations are converted directly to `NoteEvent` values. The workspace is removed after success and after controlled failures.

## Runtime settings

```text
instrument:        saxophone
sample rate:       16000 Hz
device:            cpu
batch size:        8
onset threshold:   0.3
offset threshold:  0.3
frame threshold:   0.1
```

The result records sample rate, device, all thresholds, model identity, model revision, checkpoint filename, and verified checkpoint digest.

## Checkpoint verification

The resolver requests only the pinned model ID, revision, and filename. Before model initialization it:

1. requires an exact size of `99341469` bytes;
2. calculates SHA-256 using bounded reads;
3. requires the exact pinned digest;
4. refuses to load the checkpoint after any mismatch.

The checkpoint is an external PyTorch `.pth` file. It is never committed, embedded in fixtures, exposed in a public result, or copied into a final artifact. Cache and temporary paths are not included in controlled error messages.

## Event conversion and deterministic order

External fields map as follows:

```text
midi_note   → pitch_concert_midi
onset_time  → onset_seconds
offset_time → offset_seconds
velocity    → velocity
activation  → confidence
```

External numerical scalar types, including NumPy scalar values, are converted to ordinary Python `int` or `float` values at the infrastructure boundary. No value is rounded, clipped, corrected, merged, or silently replaced. `NoteEvent` schema `1.0` remains the source of pitch, timing, velocity, and confidence validation.

The adapter returns events ordered by:

```text
onset_seconds
pitch_concert_midi
offset_seconds
velocity
```

Duplicates and overlaps are preserved. SAX-021 performs no minimum-duration filtering, deduplication, merging, overlap correction, or low-confidence filtering.

## Confidence

```text
source: reg_onset_output
frames_per_second: 100
begin_midi_note: 21
center_frame: round(onset_seconds * 100)
window: center_frame ± 2
method: max_reg_onset_activation_pm2_frames
```

For the event pitch, the adapter reads the maximum finite activation in the clipped five-frame window centered on the rounded onset frame. The activation matrix must be two-dimensional, indexable, finite, and within `0.0..1.0` for every inspected value.

**Confidence es una activación interna del baseline y no una probabilidad calibrada de que la nota sea correcta.**

No confidence threshold is applied. Low-confidence policy belongs to SAX-023.

## Controlled failures

```text
TranscriptionEngineUnavailableError
TranscriptionCheckpointDownloadError
TranscriptionCheckpointMismatchError
TranscriptionModelInitializationError
TranscriptionInferenceError
InvalidTranscriptionEngineOutputError
```

The errors identify the failed stage without exposing uploaded audio, activation arrays, cache paths, temporary paths, or HTTP details. Upstream exceptions remain available through exception chaining.

The runtime contains a narrow compatibility boundary for deprecation warnings emitted transitively by `audioread` while importing `aifc`, `audioop`, and `sunau` on Python 3.11. Unrelated warnings remain errors; the repository-wide warning gate is not relaxed.

## Real integration fixture

The integration test generates an approximately two-second WAV in memory containing a 440 Hz fundamental, second and third harmonics, fade-in/fade-out, and mild vibrato. No third-party audio is downloaded or committed. The test requires a non-empty valid result, a pitch in a robust range around A4, successful schema serialization, exact checkpoint provenance, and temporary cleanup. It deliberately avoids exact assertions for event count, timing, velocity, confidence, or runtime duration.

## Compatibility and limitations

Validated inference compatibility is Python 3.11 on CPU. Python 3.12 and 3.13 validate the core and FFmpeg integrations but skip the real baseline.

This smoke test is not an accuracy benchmark. SAX-021 provides no labeled-dataset evaluation, F1 metric, onset/offset tolerance study, second baseline, model selection, training, fine-tuning, persistent activations, final product MIDI, MusicXML, queue, worker, or storage integration.

The baseline is not instantiated by `main.py`, is not imported by API routes, and is not connected to any FastAPI endpoint. SAX-022 owns later event post-processing and SAX-023 owns low-confidence policy.
