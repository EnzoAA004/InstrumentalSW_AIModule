# TDD iteration 022 — Monophonic audio-to-score processor

## Story boundary

SAX-036 connects the already implemented solo-saxophone stages behind the SAX-072 `TranscriptionJobProcessor` port.

No new transcription model or notation algorithm is introduced.

## Exact base

```text
77a9dc7075c0c50e48b7da66557537e3771ee329
feature/SAX-036-monophonic-end-to-end-processor
```

## RED

The first commit contains behavior tests only:

```text
05fd6f2 test(SAX-036): define monophonic end-to-end processor
```

The expected RED is missing `MonophonicTranscriptionProcessor` and `TerminalProcessingError`.

The tests define four product invariants:

1. a normal solo transcription creates revision-zero review + MIDI + MusicXML + SVG;
2. insufficient tempo evidence uses the explicit 120 BPM fallback;
3. a controlled SVG failure preserves MIDI and MusicXML;
4. invalid source audio is terminal and does not consume worker retries.

## GREEN

The implementation composes the existing converter, model adapter, event rules, confidence annotation, transposition, tempo resolution, quantization and exporters.

`TerminalProcessingError` extends the worker contract so deterministic source failures bypass retry while still respecting the SAX-072 attempt-ownership guard.

## Integration

A separate integration test runs a generated saxophone-like WAV through the real external adapters. It is marked `baseline_integration` so Python 3.11 CI exercises the pinned FiloSax runtime while environments without the optional baseline follow the established skip policy.

The baseline integration test and the full processor E2E now use the same fixture from `tests/synthetic_audio.py`. The fixture is generated programmatically in memory, is deterministic, and contains no third-party audio.

The final integration pass validates the real pinned FiloSax baseline on CI Python 3.11 and drives the full processor to revision zero plus registered MIDI, MusicXML and SVG artifacts.

`MonophonicProcessingDiagnostics` was added as a test/observability hook. It records stage counts and artifact sizes for canonical audio, raw baseline output, post-processing, confidence, written pitch, tempo, quantization, MIDI, MusicXML and SVG rendering. It is optional and does not alter product behavior.

Final Quality is green:

- Ruff lint;
- Ruff format check;
- strict mypy;
- full protected Quality, including the Python 3.11 real-baseline integration path.

## REFACTOR constraints

- orchestration remains model-independent behind existing ports;
- artifact IDs and filenames are deterministic;
- the processor does not expose storage URLs;
- rendering degradation catches only controlled renderer failures;
- automatic tempo failures other than insufficient evidence are not hidden;
- no source-separation or multiinstrument behavior enters the story.
