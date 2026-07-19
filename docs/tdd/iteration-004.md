# TDD iteration 004 — SAX-011

## Scope

Implement an internal, reusable canonical-audio conversion capability for the AI module. The converter accepts MP3 or WAV bytes through a generic binary stream, writes a WAV PCM artifact to a caller-provided destination, and records reproducible metadata.

This iteration deliberately does **not** connect preprocessing to `POST /api/v1/transcriptions` or `GET /api/v1/transcriptions/{job_id}`. It does not classify corrupt audio, change job state, persist artifacts, or implement SAX-012.

## Requirements and traceability

```text
SAX-011
→ RF-020 canonical internal format
→ RF-021 logical reference to the original
→ RF-022 partial: channels and sample rate normalized; amplitude normalization not implemented
→ RF-023 exact preprocessing settings and FFmpeg version recorded
→ tests/unit/test_audio_preprocessing.py
→ tests/integration/test_ffmpeg_audio_converter.py
```

The repository does not currently contain the central `backlog/traceability.csv` referenced by the consolidated documentation, so this relationship is recorded here and in the pull request instead of creating a stale duplicate backlog.

## Resolution for amplitude normalization

RF-022 is only partially implemented in SAX-011. Channel count and sample rate are configurable and normalized. Amplitude processing is explicitly recorded as:

```text
amplitude_normalization = "none"
```

No peak normalization, volume normalization, LUFS calculation, `loudnorm`, or other loudness processing is present. The explicit value distinguishes a deliberate absence of amplitude normalization from an unknown configuration.

## Architecture

```text
BinaryStream                     BinaryDestination
      │                                  ▲
      ▼                                  │
ConvertToCanonicalAudio ── CanonicalAudioConverter
                                      │
                                      ▼
                        FfmpegCanonicalAudioConverter
                                      │
                          subprocess + temporary files
```

Responsibilities remain separated:

- domain contains immutable settings, original references, result, and metadata;
- application contains the use case and small protocols;
- infrastructure owns FFmpeg, `subprocess`, `wave`, and temporary paths;
- FastAPI does not participate in conversion;
- the existing API composition root does not construct or invoke the converter.

## Canonical representation

Default settings:

```text
container:                 wav
codec:                     pcm_s16le
sample_rate_hz:            16000
channels:                  1
sample_width_bits:         16
amplitude_normalization:   none
schema_version:            1.0
```

`sample_rate_hz` accepts positive integers. `channels` accepts `1` or `2`. Container, codec, sample width, amplitude mode, and schema version are fixed for this story. Invalid settings fail while constructing the immutable settings object, before an FFmpeg executor can be called.

## Original reference

`OriginalAudioReference` stores only:

```text
filename
size_bytes
audio_sha256
```

The same immutable reference is returned in `CanonicalAudioResult`. It contains no local path, binary content, public URL, FastAPI object, or storage-specific identifier.

## RED

The first local test execution occurred before production modules were created:

```text
python -m pytest \
  tests/unit/test_audio_preprocessing.py \
  tests/integration/test_ffmpeg_audio_converter.py

collected 0 items / 2 errors
ModuleNotFoundError: No module named 'saxo_ai.application.audio_preprocessing'
ModuleNotFoundError: No module named 'saxo_ai.application.audio_preprocessing'
RED_EXIT_CODE=2
```

The unit and integration contracts were published before any production code in the branch.

A second test-first cycle protected the CI requirement before modifying the workflow:

```text
python -m pytest tests/quality/test_quality_configuration.py

1 failed, 10 passed
KeyError: 'env'
CI_RED_EXIT_CODE=1
```

The missing contract was `SAXO_REQUIRE_FFMPEG=1` plus explicit FFmpeg installation and version reporting in the existing matrix job.

## GREEN

The minimum implementation added:

- immutable canonical settings, metadata, result, and original reference;
- `BinaryDestination` and `CanonicalAudioConverter` application ports;
- `ConvertToCanonicalAudio` use case;
- an FFmpeg adapter using standard-library `subprocess`;
- stable errors for missing FFmpeg, timeout, non-zero exit, absent output, invalid WAV, and invalid settings;
- bounded source materialization and bounded destination copy;
- semantic WAV validation using the standard-library `wave` module;
- real WAV and MP3 integration tests generated from synthetic signals;
- explicit FFmpeg installation and enforcement in GitHub Actions.

The initial focused GREEN result was:

```text
20 passed in 1.92s
```

## REFACTOR

- duplicated source/output read loops were centralized in one bounded chunk iterator;
- defaults are named constants;
- the original source requires only `read(size)` and is never sought, written, truncated, or inspected for a path;
- temporary filenames are fixed internal names and never derive from the user filename;
- output is copied only after FFmpeg succeeds and semantic validation passes;
- temporary directories are context-managed and cleaned on success and exceptions;
- public results expose no path;
- application and domain remain free of FastAPI;
- domain remains free of `subprocess`, `tempfile`, and filesystem paths;
- the existing endpoint and composition-root files have no SAX-011 changes.

## Bounded streams and memory behavior

```text
DEFAULT_IO_CHUNK_SIZE = 64 * 1024
```

The input is copied to a controlled temporary file through repeated `source.read(65536)` calls. FFmpeg reads that temporary file. The generated WAV is validated from disk and copied to the caller's destination in the same bounded chunk size.

Neither the complete MP3/WAV input nor the complete converted WAV is deliberately loaded into one Python `bytes` object. The original stream need not support `seek`, `tell`, `fileno`, or a path.

## Temporary workspace

Each conversion uses `TemporaryDirectory` with internal names equivalent to:

```text
<temporary-workspace>/source.bin
<temporary-workspace>/canonical.wav
```

The user filename is not used in either path or in the FFmpeg order. Context-manager cleanup runs after success and after controlled errors. Tests retain observed temporary paths and verify that their directories no longer exist after conversion or failure.

## Sanitized FFmpeg orders

Version discovery:

```text
ffmpeg -version
```

Conversion order, with temporary values sanitized:

```text
ffmpeg
-hide_banner
-loglevel error
-y
-i <temporary-workspace>/source.bin
-map 0:a:0
-vn
-map_metadata -1
-ac <channels>
-ar <sample_rate_hz>
-c:a pcm_s16le
-f wav
<temporary-workspace>/canonical.wav
```

Arguments are passed as a list with `shell=False` and an explicit configurable timeout. The converter does not use `subprocess.run(input=complete_audio_bytes)`.

## FFmpeg version

Local integration was executed with:

```text
ffmpeg version 7.1.3-0+deb13u1 Copyright (c) 2000-2025 the FFmpeg developers
```

The public metadata records the normalized first non-empty line from the real `ffmpeg -version` output. It does not expose the executable path.

## WAV validation

The converted artifact is opened with `wave` and must satisfy:

```text
compression type = NONE
sample width = 2 bytes
sample rate = requested sample_rate_hz
channels = requested channels
frames > 0
duration = frames / sample_rate
```

Full binary snapshots are intentionally avoided because semantically valid WAV bytes may differ between FFmpeg versions.

## Duration tolerance and measured results

The initial common tolerance is:

```text
maximum absolute difference = 0.10 seconds
```

Measured local results for one-second synthetic fixtures:

```text
WAV default:       1.000000 s, difference 0.000000 s
WAV 22050/stereo:  1.000000 s, difference 0.000000 s
MP3 default:       1.000000 s, difference 0.000000 s
```

Each produced artifact also passed:

```text
ffmpeg -v error -i canonical.wav -f null -
```

with exit code `0`.

## Unit tests

Unit tests use fake non-seekable sources, bounded destinations, and a recording command executor. They cover:

- default and alternative settings;
- invalid sample rates, channels, and fixed options;
- preservation of the original reference;
- bounded source reads and destination writes;
- argument-list construction, `shell=False`, and timeout propagation;
- version metadata;
- missing FFmpeg;
- timeout;
- non-zero conversion exit and sanitized/truncated stderr;
- missing output;
- invalid WAV output;
- temporary cleanup;
- architecture and absence of API integration.

Final local non-integration result:

```text
57 passed, 3 deselected in 0.37s
```

These tests do not require FFmpeg.

## Integration tests

Real integration fixtures are generated during pytest using only `wave`, `math`, and `struct`. No downloaded or third-party audio blobs are stored.

The integration suite validates:

- synthetic stereo 44.1 kHz A4 WAV → default mono 16 kHz PCM16 WAV;
- synthetic mono 32 kHz silence WAV → 22.05 kHz stereo PCM16 WAV;
- FFmpeg-generated MP3 → default mono 16 kHz PCM16 WAV;
- semantic validation with `wave`;
- independent external FFmpeg decoding;
- bounded reads from a non-seekable source;
- original-reference preservation.

Final local result:

```text
3 passed, 57 deselected in 2.03s
skips: 0
```

When FFmpeg is absent locally, these tests skip with a clear reason. When `SAXO_REQUIRE_FFMPEG=1`, absence is a failure. CI always uses the required mode.

## Final local verification

Environment:

```text
Python 3.13.5
FFmpeg 7.1.3-0+deb13u1
```

Results:

```text
python -m pip install -e ".[dev]"
Successfully built instrumentalsw-ai-module
Successfully installed instrumentalsw-ai-module-0.1.0

python -m pytest -m "not integration"
57 passed, 3 deselected in 0.37s

python -m pytest -m integration
3 passed, 57 deselected in 2.03s

python -m pytest
60 passed in 2.13s

python -m pytest --cov=saxo_ai --cov-report=term-missing --cov-report=xml
60 passed in 2.90s
Coverage XML written to file coverage.xml
Required test coverage of 90.0% reached
Total coverage: 92.38%

python -m ruff check src tests scripts
All checks passed!

python -m ruff format --check src tests scripts
27 files already formatted

python -m mypy
Success: no issues found in 27 source files
```

The shared command also passes:

```text
python scripts/check_quality.py
Quality gate passed.
```

## CI

The workflow keeps the protected job names:

```text
Python 3.11
Python 3.12
Python 3.13
```

Each matrix job installs FFmpeg using Ubuntu's package manager, prints `ffmpeg -version`, exports `SAXO_REQUIRE_FFMPEG=1`, installs the project, and runs the unchanged shared quality command. Final remote results are recorded in the pull request after the draft workflow completes.

## Limitations and stories not implemented

- RF-022 amplitude normalization remains partial and explicit as `none`.
- No loudness, LUFS, `loudnorm`, peak, or volume normalization.
- No converter invocation from FastAPI or `CreateTranscriptionJob`.
- No job-state changes or `FAILED` state.
- No classification of corrupt audio and no SAX-012 behavior.
- No permanent original or canonical artifact storage.
- No object storage, PostgreSQL, Redis, queues, workers, Docker, limits, models, inference, training, datasets, MIDI, or MusicXML.
- Backend and Frontend remain unchanged.
