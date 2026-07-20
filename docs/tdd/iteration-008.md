# TDD iteration 008 — SAX-021

## Scope and architecture

SAX-021 adds the first real isolated-saxophone audio-to-note baseline behind
`TranscriptionEngine` and `TranscribeCanonicalAudio`. `HfSaxophoneTranscriptionEngine` returns a
`TranscriptionResult` containing `NoteEventBatch` schema `1.0`, model identity, source revision,
checkpoint identity, and settings. FastAPI, persistence, SAX-022, and SAX-023 remain outside scope.

## Complete provenance

```text
hf-midi-transcription
  version: 0.1.1
  source revision: 96f6797881e9497cbfc8f8e5deccea9c1f2f7adc

piano-transcription-inference
  installed version: 0.1.0
  source revision: 7568dc7f78b625e40cf9776e2806d164006610e3

model revision: 982ce108d7010bc3c4f36cf851caea8d4c94763d
checkpoint: filosax_25k.pth, 99341469 bytes
SHA-256: 448cf2c8ea6d4b77f7435f5b9a496211ea60300c5c17fa9c754da764f75f3a6a
```

Package version, Git source revision, model revision, and checkpoint checksum are separate
provenance dimensions.

## Original RED–GREEN–REFACTOR

Original RED commits:

```text
0b786aa  test(SAX-021): define replaceable transcription engine contract
1726567  test(SAX-021): define FiloSax baseline integration
e926369  test(SAX-021): define pinned baseline adapter contracts
```

The original RED produced three import errors. GREEN added the port/use case, immutable result
contracts, bounded non-seekable streams, exact checkpoint verification, temporary cleanup,
controlled failures, deterministic order, confidence derivation, and real CPU inference.

Real inference then reproduced external `numpy.float32` values. Commit `0fbd535` normalizes finite
external numerical scalars to Python `int`/`float` without rounding, merging, filtering, or changing
`NoteEvent` schema `1.0`.

## Transitive reproducibility RED

FiloSax metadata still declared a floating Git dependency on
`piano-transcription-inference`. Tests-only commit:

```text
b15b42e  test(SAX-021): require pinned transitive baseline runtime
```

Exact result:

```text
11 failed, 4 passed
```

The tests require full 40-character VCS revisions, exact PEP 610 URL and `commit_id`, controlled
failures for missing/malformed/wrong metadata, no installation-path leakage, and prevention of
model initialization after mismatch.

## Installation GREEN

Declaring both exact references in `.[dev,baseline]` failed in clean Python 3.11 because the
upstream package still requested its floating piano reference. The pin was not removed.

The final command is:

```bash
python scripts/install_baseline.py
```

The installer uses `sys.executable`, never `shell=True`, disables pip cache, installs runtime
dependencies, force-reinstalls both exact Git distributions with `--no-deps`, propagates exit
codes, and verifies PEP 610 after installation. Focused GREEN reached `63 passed`.

Before checkpoint resolution or PyTorch initialization, runtime verification requires exact
version, repository URL, Git VCS, full commit ID, and expected commit for both distributions.
Mismatch raises `TranscriptionEngineUnavailableError` without exposing full JSON or paths.

## Piano version clarification

The legacy `setup.py` contains `0.0.5`, but the PEP 621 `pyproject.toml` in the same pinned commit
declares `0.1.0`. Modern pip installs version `0.1.0`. CI verified that version together with the
exact URL and commit `7568dc7f78b625e40cf9776e2806d164006610e3`; the commit was never relaxed.

## Confidence and real inference

```text
source: reg_onset_output
frames_per_second: 100
begin_midi_note: 21
center_frame: round(onset_seconds * 100)
window: center_frame ± 2
method: max_reg_onset_activation_pm2_frames
```

Confidence is an internal activation, not a calibrated probability. Duplicates and overlaps are
preserved. A diagnostic run produced two events; the first was pitch 68, onset 1.191704, offset
1.200000, velocity 127, confidence 0.324814. These are evidence, not exact assertions.

## Local final results

Python 3.13.5 with FFmpeg; real Python 3.11 runtime absent locally:

```text
pip install -e ".[dev]"                success
scripts/check_quality.py                280 passed, 1 skipped; 91.72%
pytest                                  280 passed, 1 skipped
pytest -m "not integration"             271 passed, 10 deselected
pytest -m integration                   9 passed, 1 skipped
pytest -m baseline_integration          1 skipped
ruff check                              passed
ruff format --check                     58 files formatted
mypy                                    no issues in 58 files
```

## Final clean matrix

```text
Quality #97 — Run ID 29754717761
Python 3.11 — success: clean controlled install, both PEP 610 checks, real CPU inference, full gate
Python 3.12 — success: core and FFmpeg gate; explicit baseline skip
Python 3.13 — success: core and FFmpeg gate; explicit baseline skip
```

Protected job names, `contents: read`, 20-minute timeout, and 90% coverage threshold remain
unchanged. The final workflow contains no diagnostic artifacts, `continue-on-error`, or artificial
failure steps.

## Not implemented

No SAX-022 deduplication, merging, minimum duration, or overlap correction; no SAX-023 threshold;
no second baseline, training, datasets, final MIDI, MusicXML, HTTP wiring, job transition, queue,
worker, persistence, Backend, or Frontend changes.
