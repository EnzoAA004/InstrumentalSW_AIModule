# TDD iteration 008 — SAX-021

## Scope

Integrate the first real, pinned audio-to-note baseline for isolated saxophone behind a replaceable application port and use case. Convert raw baseline output and onset activations into the existing `NoteEventBatch` schema `1.0` while recording complete result-level provenance.

This iteration does not connect FastAPI, change job state, persist audio/MIDI/activations, or implement SAX-022/SAX-023 policy.

## Contracts and architecture

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

`TranscriptionEngine` requires only:

```python
def transcribe(source: BinaryStream) -> TranscriptionResult: ...
```

`TranscribeCanonicalAudio` delegates once, preserves the stream and result, and propagates controlled engine errors. Domain and application do not import FastAPI, Hugging Face, PyTorch, or `hf_midi_transcription`.

## Pinned baseline

```text
package:             hf-midi-transcription
reported version:    0.1.1
source commit:       96f6797881e9497cbfc8f8e5deccea9c1f2f7adc
model ID:            xavriley/midi-transcription-models
model revision:      982ce108d7010bc3c4f36cf851caea8d4c94763d
checkpoint:          filosax_25k.pth
checkpoint size:     99,341,469 bytes
checkpoint SHA-256:  448cf2c8ea6d4b77f7435f5b9a496211ea60300c5c17fa9c754da764f75f3a6a
sample rate:         16000 Hz
device:              CPU
```

The reported `0.1.1` package is installed from the fixed official source commit because no usable PyPI distribution exists for this integration. The dependency is optional and constrained to Python 3.11.

## RED

Tests were committed before production code:

```text
0b786aa  test(SAX-021): define replaceable transcription engine contract
1726567  test(SAX-021): define FiloSax baseline integration
e926369  test(SAX-021): define pinned baseline adapter contracts
```

Exact RED:

```text
python -m pytest \
  tests/unit/test_transcription_engine.py \
  tests/unit/test_hf_saxophone_adapter.py \
  tests/integration/test_hf_saxophone_baseline.py

collected 0 items / 3 errors
ModuleNotFoundError: No module named 'saxo_ai.application.transcription'
ModuleNotFoundError: No module named 'saxo_ai.application.transcription_errors'
ModuleNotFoundError: No module named 'saxo_ai.infrastructure.hf_saxophone'
RED_EXIT_CODE=2
```

## GREEN

The minimum implementation added:

- immutable identity, settings, and result contracts;
- `TranscriptionEngine` and `TranscribeCanonicalAudio`;
- controlled dependency/download/checksum/initialization/inference/output errors;
- fixed checkpoint resolution and pre-load verification;
- deferred optional runtime imports;
- bounded materialization of non-seekable streams;
- activation-based confidence conversion;
- deterministic ordering without filtering;
- a generated real integration fixture.

Focused GREEN first reached:

```text
46 passed, 1 skipped
```

The skip was the expected real baseline integration in local Python 3.13 without the optional extra.

## Real NumPy scalar defect

Real Python 3.11 inference initialized the checkpoint and produced events, but the external runtime returned timing values as NumPy scalar types such as `numpy.float32`. `NoteEvent` intentionally accepts ordinary Python numerical values and rejected that representation at the adapter boundary.

The real integration test reproduced the failure after inference. The correction normalizes only finite external representations:

```text
external Integral → Python int
external Real     → Python float
```

It does not round, clamp, repair, merge, or filter values. Invalid pitch, velocity, timing, confidence, NaN, and infinities continue to fail through `NoteEvent` schema `1.0`.

```text
0fbd535  fix(SAX-021): normalize external numeric scalar types
```

## Confidence and ordering

```text
source: reg_onset_output
frames_per_second: 100
begin_midi_note: 21
center_frame: round(onset_seconds * 100)
window: center_frame ± 2
method: max_reg_onset_activation_pm2_frames
```

Confidence is an internal activation, not a calibrated probability. No threshold is applied.

Events are sorted by onset, pitch, offset, and velocity. Duplicates and overlaps are preserved. SAX-021 performs no deduplication, merging, minimum-duration filtering, overlap correction, or low-confidence filtering.

## Checkpoint and temporary-file guarantees

The resolver requests only the pinned model ID, revision, and filename. Exact size and SHA-256 are checked with bounded reads before model initialization. A mismatch prevents runtime construction and controlled errors omit cache and temporary paths.

The adapter requires only `read(size) -> bytes`; it does not require seekability, a filename, or a FastAPI type. Canonical WAV and the external runtime's MIDI path live in a context-managed temporary directory that is removed after success and controlled failures. The MIDI is not a final product artifact.

## Synthetic fixture

The real integration generates approximately two seconds of 16 kHz mono PCM16 audio in memory with a 440 Hz fundamental, second and third harmonics, fade-in/fade-out, and mild vibrato. No third-party audio is downloaded or committed. Assertions intentionally avoid exact event counts, timings, velocities, confidences, and runtime durations.

## Run #57

`Quality #57`, run ID `29717961924`, was not a successful matrix. It demonstrated:

- baseline installation in Python 3.11;
- exact checkpoint download and verification;
- CPU initialization and real inference;
- successful conversion after NumPy normalization;
- 259 passed tests;
- 92.72% coverage.

The quality gate was incomplete because Ruff reported E501 in `transcription_errors.py`, and the workflow was deliberately red for diagnostics. It is recorded as **successful inference and tests, incomplete quality gate, diagnostic workflow intentionally red**.

## Ruff correction and diagnostic removal

The conditional error message was formatted without an E501 exclusion or a larger line limit. A later Ruff-version difference identified five formatting-only files; exact CI formatter output was applied without behavioral changes.

All final `continue-on-error`, redirected logs, artifact uploads, checkout exports, and artificial failure steps were removed. The definitive workflow fails directly on installation or quality failure.

## REFACTOR

- `hf_baseline_contract.py`: fixed identity and external protocols;
- `hf_checkpoint.py`: download and verification;
- `hf_runtime.py`: optional runtime and narrow warning compatibility;
- `hf_output.py`: external scalar, activation, and event normalization;
- `hf_saxophone.py`: orchestration only;
- exact transitive `aifc`, `audioop`, and `sunau` deprecations from `audioread` are isolated;
- unrelated warnings remain errors;
- diagnostics are emitted through an observer, not stored in domain events;
- audio, tensors, activations, and final MIDI are not retained.

## Real inference evidence

A diagnostic execution on the same functional implementation recorded:

```text
cache status:           download
download seconds:       1.582226
verification seconds:   0.070752
initialization seconds: 27.613063
inference seconds:      3.279791
produced events:        2
first pitch:            68
first onset:            1.191704
first offset:           1.200000
first velocity:         127
first confidence:       0.324814
```

These values are diagnostic evidence, not golden assertions or performance targets. Clean run `29720266512` repeated the required Python 3.11 installation and real integration successfully.

## Local final results

Environment:

```text
Python 3.13.5
Ruff 0.15.22
FFmpeg available
baseline extra not installed
```

```text
python -m pip install -e ".[dev]"
→ success

python scripts/check_quality.py
→ 258 passed, 1 skipped
→ coverage 91.03%
→ Ruff lint passed
→ Ruff format: 54 files already formatted
→ mypy: no issues in 54 source files
→ quality gate passed

python -m pytest
→ 258 passed, 1 skipped

python -m pytest -m "not integration"
→ 249 passed, 10 deselected

python -m pytest -m integration
→ 9 passed, 1 skipped, 249 deselected

python -m pytest -m baseline_integration
→ 1 skipped, 258 deselected

python -m pytest --cov=saxo_ai --cov-report=term-missing --cov-report=xml
→ 258 passed, 1 skipped
→ coverage 91.03%; coverage.xml written

python -m ruff check src tests scripts
→ all checks passed

python -m ruff format --check src tests scripts
→ 54 files already formatted

python -m mypy
→ success; no issues in 54 source files
```

Explicit local skip reason:

```text
hf-midi-transcription baseline extra is not installed; Python 3.11 CI requires it
```

The real model did not run locally. Python 3.11 CI is the mandatory real-inference evidence.

## Clean functional CI

```text
Quality #74
Run ID: 29720266512
```

```text
Python 3.11 — success
- installed .[dev,baseline]
- required FFmpeg and baseline integration
- real CPU inference completed
- pytest, coverage, Ruff, format, and mypy passed

Python 3.12 — success
- installed .[dev]
- explicit baseline skip
- FFmpeg integrations and full core quality gate passed

Python 3.13 — success
- installed .[dev]
- explicit baseline skip
- FFmpeg integrations and full core quality gate passed
```

Protected names remain `Python 3.11`, `Python 3.12`, and `Python 3.13`; permissions remain `contents: read`; timeout remains 20 minutes.

## Coverage

```text
Python 3.11 with real baseline: 92.72%
Python 3.12/3.13 and local:     91.03%
required threshold:             90%
```

The threshold was not lowered.

## Limitations and stories not implemented

- no SAX-022 deduplication, merging, minimum duration, or overlap resolution;
- no SAX-023 threshold or low-confidence marker;
- no second baseline or Basic Pitch;
- no training, datasets, metrics, or accuracy claims;
- no persistent activations, final MIDI, or MusicXML;
- no HTTP endpoint, FastAPI wiring, or job transition;
- no queue, worker, database, storage, retries, or Docker;
- Backend and Frontend are unchanged.
