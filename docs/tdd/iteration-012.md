# TDD iteration 012 — SAX-031

## Scope

Implement an internal and deterministic Standard MIDI File exporter after SAX-030.

The story is:

> As a user, I want a valid MIDI file from the transcription so I can play it and open it in external tools.

Acceptance scope:

- configurable tempo;
- deterministic event ordering;
- no negative durations or delta times;
- external MIDI parser validation;
- structural snapshot;
- preserved provenance;
- no FastAPI, persistence, Backend, or Frontend integration.

The implementation intentionally excludes SAX-032 tempo estimation, SAX-033 quantization, SAX-034 MusicXML, playback, synthesis, storage, endpoints, jobs, workers, and queues.

## Initial RED

Tests-only commits preceded all production implementation:

```text
317d183  test(SAX-031): define MIDI export contracts
65d2081  test(SAX-031): define MIDI export use case
b983ef7  test(SAX-031): define interoperable MIDI file output
590b2fa  test(SAX-031): correct MIDI message count contract
717034a  test(SAX-031): correct input error contracts
7eee5db  test(SAX-031): type-check external Mido parser tests
```

The first focused execution failed during collection for the expected missing capability:

```text
3 errors during collection

ModuleNotFoundError: No module named 'saxo_ai.domain.midi_export'
ModuleNotFoundError: No module named 'saxo_ai.application.midi_export'
ModuleNotFoundError: No module named 'saxo_ai.infrastructure.mido_midi'

RED_EXIT_CODE=2
```

This established the domain contracts, application port/use case, and external Mido adapter boundary before implementation.

## Initial GREEN

The minimum implementation was introduced through:

```text
ba534c8  feat(SAX-031): add pinned Mido dependency and test marker
a920e62  feat(SAX-031): add MIDI export settings and artifact contracts
9da4442  feat(SAX-031): add MIDI encoder port and export use case
12e7140  feat(SAX-031): encode type-one MIDI with Mido
```

Initial focused verification on the reconstructed Python 3.13 workspace produced:

```text
74 passed
```

The implementation established:

- `MidiExportSettings`, plan, report, artifact, and result contracts;
- `MidiFileEncoder` application port;
- `ExportWrittenPitchToMidi` use case;
- Mido `1.3.3` infrastructure adapter;
- type-one Standard MIDI File with 480 ticks per beat and two tracks;
- concert-pitch playback;
- velocity-zero and minimum-one-tick technical adaptations;
- deterministic absolute and delta ordering;
- external parser, binary snapshot, and temporary-file interoperability checks.

## REFACTOR before full-suite diagnosis

Naming and contracts were refined without expanding scope. The source provenance chain remained object-reference based, and Mido remained isolated in infrastructure.

The sandbox could not perform a normal GitHub clone because outbound DNS resolution for `github.com` was unavailable, and the `gh` executable was not installed. Focused files were reconstructed through the authenticated GitHub connector. Therefore no complete local editable installation or full local quality gate is claimed.

## Full-suite failure — Quality #144

The protected matrix run was:

```text
workflow: Quality #144
run ID:   29785687253

Python 3.11 — failure inside quality gate
Python 3.12 — failure inside quality gate
Python 3.13 — failure inside quality gate
```

All dependency installation steps completed. The available Actions log view truncated the final pytest output, so no production or test change was made from a hypothesis.

## Temporary diagnostic mechanism

A temporary workflow was added at:

```text
.github/workflows/sax031-diagnostics.yml
```

It ran on Ubuntu 24.04 with Python 3.13, installed FFmpeg and the normal project dependencies, executed the four quality controls separately, captured stdout/stderr and exit codes, always uploaded them as an artifact, and propagated the first non-zero result.

Initial diagnostic commit:

```text
9db2552  ci(SAX-031): capture isolated quality diagnostics
```

Because the available connector enumerated pull-request-triggered workflow runs, the temporary workflow was also exposed on the current pull request. The protected `.github/workflows/quality.yml` remained unchanged.

Diagnostic evidence:

```text
run ID:       29789411017
artifact:     sax031-quality-diagnostics
artifact ID:  8479679345
```

Exit files:

```text
pytest-coverage.exit = 1
ruff-lint.exit       = 0
ruff-format.exit     = 0
mypy.exit            = 0
```

First failing command:

```bash
python -m pytest --cov=saxo_ai --cov-report=term-missing --cov-report=xml
```

Exact failing test:

```text
tests/unit/test_audio_hashing.py::test_architecture_keeps_framework_and_hashlib_dependencies_outward
```

Exact violation:

```text
src/saxo_ai/domain/midi_export.py
from hashlib import sha256
```

Full diagnostic summary:

```text
1 failed, 555 passed, 1 skipped
```

## Root cause

`MidiArtifact` recalculated SHA-256 inside the domain contract. The project already has a global architecture rule that hashing dependencies remain outside domain.

The MIDI use case also calculated the same digest in application. The domain therefore contained an unnecessary infrastructure-like implementation dependency and duplicated responsibility.

Mido installation, Mido availability, FFmpeg, Python version support, and the FiloSax baseline were not causal.

## Additional RED

The full-suite defect was converted into a focused regression before production changed:

```text
b542296  test(SAX-031): reproduce full-suite MIDI export failure
```

The new test asserted that:

```text
hashlib is absent from domain/midi_export.py
hashlib.sha256 remains owned by application/midi_export.py
```

An application behavior test was then committed before the new constructor existed:

```text
cb1ace0  test(SAX-031): define application-owned artifact digest
```

It required an application function to construct artifact metadata and calculate the exact digest from the encoded bytes.

Focused RED evidence:

```text
run ID:       29789610230
artifact ID:  8479750546
result:       1 failed
```

The failure was the expected domain `hashlib` import. Ruff lint and mypy were already green. Ruff format identified only the newly added regression test, which was later formatted with the repository configuration.

## Correction

The minimum architectural correction was:

```text
a08cf01  refactor(SAX-031): keep artifact hashing outside domain
7d62ea7  feat(SAX-031): centralize application artifact digest
```

`MidiArtifact` now validates:

- byte content and Standard MIDI File header;
- media type and extension;
- exact byte length;
- lowercase 64-character hexadecimal digest shape.

Application now owns:

```python
build_midi_artifact(content: bytes) -> MidiArtifact
```

This function computes:

```python
sha256(content).hexdigest()
```

and is the only constructor used by `ExportWrittenPitchToMidi`.

The correction did not change the encoder, parser, pitch policy, tick policy, tempo behavior, source events, or provenance.

## Contract expectation adjustment

One pre-existing SAX-031 unit case directly instantiated `MidiArtifact` with a well-shaped but incorrect digest and expected domain to recompute it. That expectation contradicted the recovered project architecture boundary.

The contract was corrected while preserving significant digest tests:

```text
b51a566  test(SAX-031): move digest consistency to application boundary
7172453  test(SAX-031): format architecture regression
```

The domain still rejects malformed digests. The new application test verifies the exact byte-to-SHA correspondence.

## Diagnostic GREEN

The full diagnostic workflow was restored after the correction and completed successfully:

```text
run ID:       29790251048
artifact ID:  8479976443
```

Results:

```text
pytest + coverage: exit 0
Ruff lint:         exit 0
Ruff format:       exit 0
mypy:              exit 0

557 passed, 1 skipped
coverage: 93.24%
80 files already formatted
Success: no issues found in 80 source files
```

The single skip was `baseline_integration` on Python 3.13, as required by the existing baseline policy.

## Diagnostic removal

The temporary diagnostic workflow was completely removed:

```text
bf88836  ci(SAX-031): remove temporary quality diagnostics
```

No diagnostic steps, flags, artifacts, or workflow files remain in the final repository tree. The protected quality workflow was never structurally modified.

## Protected matrix GREEN

The clean functional head was validated by:

```text
workflow: Quality #156
run ID:   29790326571

Python 3.11 — success
Python 3.12 — success
Python 3.13 — success
```

Python 3.11 completed:

- FFmpeg installation;
- controlled baseline installer;
- exact source revisions and PEP 610 checks;
- checkpoint size and SHA-256 validation;
- real CPU inference;
- MIDI integration;
- pytest and coverage;
- Ruff lint and format;
- strict mypy.

Python 3.12 and 3.13 completed the normal project installation, FFmpeg and MIDI integration, and the complete quality gate. Only the real baseline integration was skipped outside Python 3.11.

## Requested command verification

A second temporary workflow executed each requested command independently on Ubuntu 24.04 and Python 3.13 so results could be recorded without claiming unsupported local execution.

```text
run ID:       29790543711
artifact:     sax031-command-verification
artifact ID:  8480089667
```

Every command returned exit code zero:

```bash
python scripts/check_quality.py
python -m pytest
python -m pytest -m "not integration"
python -m pytest -m integration
python -m pytest -m midi_integration
python -m pytest -m baseline_integration
python -m pytest --cov=saxo_ai --cov-report=term-missing --cov-report=xml
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
python -m mypy
```

Recorded splits:

```text
all tests:               557 passed, 1 skipped
not integration:         541 passed, 17 deselected
integration:              16 passed, 1 skipped, 541 deselected
midi_integration:          7 passed, 551 deselected
baseline_integration:      1 skipped, 557 deselected on Python 3.13
coverage:                 93.24%
Ruff lint:                pass
Ruff format:              80 files already formatted
mypy:                     no issues in 80 source files
```

The baseline-only skip on Python 3.13 is expected. The protected Python 3.11 job provides the required real baseline execution.

The temporary command-verification workflow was then removed:

```text
46fda46  ci(SAX-031): remove temporary command verification
```

## Functional review

The final implementation retains:

```text
MIDI file type:          1
ticks per beat:          480
tracks:                  2
channel:                 0
pitch representation:    concert
default tempo:           120 BPM
Mido version:            1.3.3
```

Verified behavior:

- written pitch is not used as playback pitch;
- source velocity zero exports as one and is counted;
- positive events receive at least one tick;
- note-off precedes note-on at a shared tick;
- delta times are non-negative integers;
- overlaps remain independent and are not corrected;
- an empty batch produces valid MIDI;
- bytes and SHA-256 are deterministic;
- exact source and model provenance is preserved;
- generated bytes open from memory and a temporary `.mid` file;
- no persistence or HTTP integration exists.

## Files introduced or changed by SAX-031

Production and configuration:

```text
pyproject.toml
src/saxo_ai/domain/midi_export.py
src/saxo_ai/application/midi_export.py
src/saxo_ai/infrastructure/mido_midi.py
```

Tests:

```text
tests/unit/test_midi_export.py
tests/unit/test_midi_export_contracts.py
tests/unit/test_midi_export_validation.py
tests/unit/test_midi_export_architecture.py
tests/unit/test_midi_artifact_digest.py
tests/integration/test_midi_file_export.py
```

Documentation:

```text
docs/contracts/midi-export-v1.md
docs/tdd/iteration-012.md
README.md
```

## Stories not implemented

This iteration does not begin or partially implement:

```text
SAX-032 automatic tempo estimation
SAX-033 quantization
SAX-034 MusicXML
score rendering
playback or SoundFont
persistence or object storage
HTTP endpoint or job state
worker or queue
Backend
Frontend
```

SAX-021, SAX-022, SAX-023, and SAX-030 behavior remains unchanged except for consuming the existing SAX-030 result through the new isolated application use case.
