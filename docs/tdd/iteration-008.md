# TDD iteration 008 — SAX-021

## Scope

SAX-021 integrates the first real, pinned audio-to-note baseline for isolated saxophone behind a
replaceable application port and use case. It converts raw external events and onset activations to
`NoteEventBatch` schema `1.0` and records result-level model, source, checkpoint, and settings
provenance.

This extension completes runtime reproducibility. It does not connect FastAPI, change job state,
persist audio/MIDI/activations, or implement SAX-022/SAX-023 policy.

## Architecture and contracts

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

Domain and application do not import FastAPI, Hugging Face, PyTorch, or
`hf_midi_transcription`. `TranscriptionModelIdentity` now includes
`engine_source_revision`; `NoteEvent` and `NoteEventBatch` remain unchanged at schema `1.0`.

## Complete pinned chain

```text
hf-midi-transcription
  installed version: 0.1.1
  source URL:        https://github.com/xavriley/hf_midi_transcription.git
  source revision:   96f6797881e9497cbfc8f8e5deccea9c1f2f7adc

piano-transcription-inference
  installed version: 0.1.0
  source URL:        https://github.com/xavriley/piano_transcription_inference.git
  source revision:   7568dc7f78b625e40cf9776e2806d164006610e3

Hugging Face model
  model ID:          xavriley/midi-transcription-models
  model revision:    982ce108d7010bc3c4f36cf851caea8d4c94763d

checkpoint
  filename:          filosax_25k.pth
  size:              99341469 bytes
  SHA-256:           448cf2c8ea6d4b77f7435f5b9a496211ea60300c5c17fa9c754da764f75f3a6a

execution
  sample rate:       16000 Hz
  device:            CPU
```

Package version, Git source revision, model revision, and checkpoint checksum are different kinds
of provenance. No version string substitutes for a source commit.

## Original RED

Tests were committed before the original production code:

```text
0b786aa  test(SAX-021): define replaceable transcription engine contract
1726567  test(SAX-021): define FiloSax baseline integration
e926369  test(SAX-021): define pinned baseline adapter contracts
```

Exact original RED:

```text
collected 0 items / 3 errors
ModuleNotFoundError: No module named 'saxo_ai.application.transcription'
ModuleNotFoundError: No module named 'saxo_ai.application.transcription_errors'
ModuleNotFoundError: No module named 'saxo_ai.infrastructure.hf_saxophone'
RED_EXIT_CODE=2
```

## Original GREEN and NumPy defect

The initial implementation added immutable result contracts, `TranscriptionEngine`,
`TranscribeCanonicalAudio`, checkpoint verification, bounded handling of non-seekable streams,
controlled external-stage errors, activation-based confidence, deterministic ordering, and a
synthetic real-inference fixture.

Real Python 3.11 inference then exposed `numpy.float32` timing values. The integration reproduced
the defect before commit:

```text
0fbd535  fix(SAX-021): normalize external numeric scalar types
```

The adapter normalizes external `Integral`/`Real` scalars to ordinary Python `int`/`float` without
rounding, clipping, merging, filtering, or changing `NoteEvent` validation.

## Confidence and event policy

```text
source: reg_onset_output
frames_per_second: 100
begin_midi_note: 21
center_frame: round(onset_seconds * 100)
window: center_frame ± 2
method: max_reg_onset_activation_pm2_frames
```

Confidence is an internal activation, not a calibrated probability. Events are ordered by onset,
pitch, offset, and velocity. Duplicates and overlaps are preserved. No SAX-022 or SAX-023 policy is
implemented.

## Run #57

`Quality #57`, run ID `29717961924`, was not a successful matrix. It proved package installation,
checkpoint download and verification, CPU initialization, real inference, NumPy-normalized event
conversion, 259 passed tests, and 92.72% coverage. The quality gate remained incomplete because of
Ruff E501, and the workflow was intentionally red for diagnostics.

## Original clean matrix

`Quality #79`, run ID `29721230765`, completed successfully in Python 3.11, 3.12, and 3.13. It
validated the accepted SAX-021 behavior before the transitive-provenance defect was discovered.

## Reproducibility defect

The fixed FiloSax source metadata contained this floating dependency:

```text
piano-transcription-inference
@ git+https://github.com/xavriley/piano_transcription_inference.git
```

A future installation could therefore resolve a different piano runtime while the top-level
package, model, and checkpoint remained fixed. SAX-021 was functionally correct but not completely
reproducible.

## Reproducibility RED

Tests-only commit:

```text
b15b42e  test(SAX-021): require pinned transitive baseline runtime
```

Exact focused RED:

```text
11 failed, 4 passed
```

The failures defined these missing contracts:

- every baseline Git requirement must use a full 40-character revision;
- branches, floating URLs, vague tags, and short revisions are invalid;
- both installed distributions must provide valid PEP 610 `direct_url.json`;
- exact package version, source URL, Git VCS, and `commit_id` are required;
- missing/malformed metadata and wrong URL/revision fail with a controlled error;
- errors do not expose `site-packages` paths or the complete JSON document;
- provenance mismatch prevents model initialization;
- the result records `engine_source_revision`.

## Direct-reference experiment

The first GREEN attempt declared both exact VCS references in the optional `baseline` extra and
executed:

```bash
python -m pip install --no-cache-dir -e ".[dev,baseline]"
```

Run `29750335611` failed during Python 3.11 resolution. Pip detected incompatible direct
references because the top-level FiloSax metadata still requested the floating piano URL. The
transitive pin was not removed and the implementation did not fall back to a branch.

## Controlled installer GREEN

The final public installation command is:

```bash
python scripts/install_baseline.py
```

The cross-platform installer:

1. uses `sys.executable`;
2. never uses `shell=True`;
3. installs the core development environment without pip cache;
4. installs the required numerical/audio dependencies;
5. force-reinstalls piano from commit
   `7568dc7f78b625e40cf9776e2806d164006610e3` with `--no-deps`;
6. force-reinstalls FiloSax from commit
   `96f6797881e9497cbfc8f8e5deccea9c1f2f7adc` with `--no-deps`;
7. propagates the first non-zero subprocess code;
8. verifies both installed distributions through PEP 610 after installation.

Focused GREEN reached:

```text
63 passed
```

## Runtime PEP 610 gate

Before checkpoint resolution, temporary workspace creation, PyTorch initialization, or inference,
`HfMidiRuntimeFactory.ensure_available()` verifies for both packages:

```text
installed version
exact repository URL
vcs == git
commit_id is 40 lowercase hexadecimal characters
commit_id equals the pinned source revision
```

Missing or malformed metadata, another repository, another commit, a branch name, or an
incompatible version raises `TranscriptionEngineUnavailableError`. The error names only the
package and provenance stage.

## Piano version clarification

The repository's legacy `setup.py` contains version `0.0.5`, but the authoritative PEP 621
`pyproject.toml` in the same pinned commit declares version `0.1.0`. Modern pip builds and installs
that PEP 621 metadata. Clean Python 3.11 installation observed:

```text
package:           piano-transcription-inference
installed version: 0.1.0
source URL:        https://github.com/xavriley/piano_transcription_inference.git
commit_id:         7568dc7f78b625e40cf9776e2806d164006610e3
```

The source revision remains exactly the requested commit. The implementation verifies the actual
installed version instead of falsifying distribution metadata.

## Reproducibility REFACTOR

- centralized names, versions, repository URLs, and source revisions;
- introduced immutable `RuntimeDistributionRequirement` values;
- separated install command construction, execution, and post-install verification;
- force-reinstalls both exact VCS packages to prevent an older compatible install from surviving;
- reports safe, stage-specific provenance failures;
- adds `engine_source_revision` to result-level identity;
- preserves the existing model/checkpoint provenance and confidence calculation;
- restores the definitive workflow to one installer command without diagnostic artifacts,
  `continue-on-error`, or artificial failures.

## Real integration evidence

The synthetic fixture is approximately two seconds of 16 kHz mono PCM16 audio with a 440 Hz
fundamental, harmonics, fade, and mild vibrato. A prior diagnostic run recorded:

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

These values are evidence, not exact assertions or performance targets. The final clean matrix
again completed required real inference.

## Local final commands

Environment:

```text
Python 3.13.5
Ruff 0.15.22
FFmpeg available
pinned Python 3.11 baseline runtime not installed locally
```

Results:

```text
python -m pip install -e ".[dev]"
→ success

python scripts/check_quality.py
→ 280 passed, 1 skipped
→ coverage 91.80%
→ Ruff lint passed
→ Ruff format passed
→ mypy passed
→ quality gate passed

python -m pytest
→ 280 passed, 1 skipped

python -m pytest -m "not integration"
→ 271 passed, 10 deselected

python -m pytest -m integration
→ 9 passed, 1 skipped, 271 deselected

python -m pytest -m baseline_integration
→ 1 skipped, 280 deselected

python -m pytest --cov=saxo_ai --cov-report=term-missing --cov-report=xml
→ 280 passed, 1 skipped
→ total coverage 91.80%

python -m ruff check src tests scripts
→ all checks passed

python -m ruff format --check src tests scripts
→ all files formatted

python -m mypy
→ success
```

Explicit local skip:

```text
hf-midi-transcription baseline extra is not installed; Python 3.11 CI requires it
```

No claim is made that the real baseline ran locally.

## Final clean functional matrix

```text
Quality #97
Run ID: 29754717761
```

```text
Python 3.11 — success
- executed python scripts/install_baseline.py
- installed without pip cache
- force-reinstalled both exact Git packages
- verified versions, URLs, Git VCS, and exact PEP 610 commit IDs
- required FFmpeg and baseline integration
- real CPU inference completed and was not skipped
- full pytest/coverage/Ruff/format/mypy gate passed

Python 3.12 — success
- installed .[dev]
- baseline integration skipped explicitly
- FFmpeg integrations and full core quality gate passed

Python 3.13 — success
- installed .[dev]
- baseline integration skipped explicitly
- FFmpeg integrations and full core quality gate passed
```

Protected job names remain `Python 3.11`, `Python 3.12`, and `Python 3.13`; permissions remain
`contents: read`; timeout remains 20 minutes.

## Coverage

```text
local Python 3.13 core path: 91.80%
required threshold:         90%
Python 3.11 real baseline:  passed the same quality threshold
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
