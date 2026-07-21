# MIDI export contract v1

## Scope

SAX-031 converts an immutable `WrittenPitchTranscriptionResult` into a deterministic, in-memory Standard MIDI File artifact. The capability is internal and remains disconnected from FastAPI, jobs, persistence, Backend, and Frontend.

Policy version:

```text
MIDI_EXPORT_POLICY_VERSION = "1.0"
```

## Sounding-pitch decision

The MIDI note number always comes from the sounding concert pitch:

```python
written_event.source.event.pitch_concert_midi
```

The exporter never uses:

```python
written_event.written_pitch_midi
```

`written_pitch_midi` is retained for notation-oriented stories such as MusicXML. MIDI v1 represents the sound heard in the original recording, not the transposed notation read by the saxophonist.

No concert/written export switch exists in policy v1.

## Dependency

The normal project dependency is pinned:

```text
mido==1.3.3
```

No playback or port backend is installed. In particular, SAX-031 does not add `python-rtmidi`, `pygame`, FluidSynth, SoundFonts, `pretty_midi`, or `music21`.

Mido is imported only by infrastructure and integration tests. Domain and application contracts remain independent from Mido.

## Standard MIDI File representation

```text
file type:             1
ticks per beat:        480
track count:           2
MIDI channel:          0
pitch representation:  concert
default tempo:         120.0 BPM
media type:            audio/midi
extension:             .mid
```

### Track 0 — metadata

The first track contains, in order:

```text
track_name: Saxo Metadata
set_tempo
end_of_track
```

### Track 1 — concert notes

The second track contains:

```text
track_name: Saxo Concert Pitch
ordered note_on and note_off messages
end_of_track
```

Policy v1 emits no program change, time signature, key signature, General MIDI instrument, lyric, marker, quantization metadata, or playback configuration.

## Tempo settings

```python
@dataclass(frozen=True, slots=True)
class MidiExportSettings:
    tempo_bpm: float = 120.0
    policy_version: str = "1.0"
```

`tempo_bpm` must be a finite positive Python `int` or `float`. Booleans, strings, `None`, zero, negatives, NaN, and infinities are rejected.

The Standard MIDI File tempo value is:

```text
tempo_microseconds_per_beat = round(60_000_000 / tempo_bpm)
```

The result must fit the MIDI three-byte tempo range:

```text
1..16_777_215 microseconds per beat
```

SAX-031 only consumes a configured tempo. Automatic tempo estimation belongs to SAX-032.

## Seconds to absolute ticks

For one event time in seconds:

```text
absolute_tick
=
round(
  seconds
  * 480
  * 1_000_000
  / tempo_microseconds_per_beat
)
```

Inputs must be finite and non-negative. The converter returns a non-negative Python integer and performs no rhythmic-grid quantization.

At 120 BPM:

```text
0.0 s  →   0 ticks
0.5 s  → 480 ticks
1.0 s  → 960 ticks
```

## Technical minimum duration

A valid source `NoteEvent` always has `offset_seconds > onset_seconds`, but very short positive durations can round to the same absolute tick.

When:

```text
raw_offset_tick <= onset_tick
```

the exported offset becomes:

```text
offset_tick = onset_tick + 1
```

Each adjustment increments:

```text
minimum_tick_adjustment_count
```

This is a technical encoding safeguard, not musical quantization. Original seconds are never changed, rounded back into the source, or replaced by tick-derived timing.

## Velocity zero

MIDI note-on velocity zero is commonly interpreted as note-off. A source velocity of `0` therefore exports as:

```text
note_on velocity = 1
```

and increments:

```text
zero_velocity_adjustment_count
```

Source velocities `1..127` are preserved. The original `NoteEvent.velocity` is never mutated.

## Validated note plan

Each source event becomes one immutable `MidiNotePlan` with:

```text
source reference
source index
concert MIDI pitch
export velocity
onset absolute tick
offset absolute tick
```

Required invariants include:

```text
pitch_concert_midi matches the source concert pitch
1 <= velocity <= 127
0 <= onset_tick < offset_tick
source_index is a non-negative integer
```

The plan contains every original written event exactly once and retains each exact source object reference.

## Deterministic ordering

The plan is sorted by:

```text
onset_tick
offset_tick
pitch_concert_midi
source_index
```

The encoder expands the plan into absolute note messages and sorts by:

```text
absolute_tick
message priority
source_index
```

Message priority is:

```text
note_off before note_on at the same tick
```

This permits a note to end exactly when another begins without producing a transient overlapping note-on order.

After absolute ordering, each message time is converted to a delta from the previous absolute tick. Negative delta times are rejected.

SAX-031 does not force monophony, merge repeated pitches, shorten overlaps, or move events to a rhythmic grid. Valid overlaps remain independent note pairs.

## Port and use case

### MidiFileEncoder

The application port is structural:

```python
class MidiFileEncoder(Protocol):
    def encode(
        self,
        *,
        plan: tuple[MidiNotePlan, ...],
        settings: MidiExportSettings,
    ) -> bytes: ...
```

It receives validated contracts and returns bytes. It has no dependency on Mido, FastAPI, paths, persistence, or product state.

### ExportWrittenPitchToMidi

The application use case:

1. validates the SAX-030 result and settings;
2. reads concert pitch, timing, and velocity through the preserved source chain;
3. converts seconds to ticks;
4. applies only the technical one-tick and velocity-zero adaptations;
5. creates and sorts the immutable plan;
6. calls `MidiFileEncoder`;
7. builds exact artifact metadata in application;
8. returns the result and report.

Unexpected encoder exceptions become a controlled `MidiEncodingError`. Existing controlled encoding and artifact errors are preserved.

## Application-owned SHA-256

The existing architecture requires hashing dependencies to remain outside domain. Therefore:

- `MidiArtifact` validates bytes, header, media type, extension, size, and lowercase 64-character SHA-256 shape;
- `build_midi_artifact` in application computes the exact digest with `hashlib.sha256`;
- the use case only returns artifacts created through that application function.

This keeps the exact content-to-digest calculation out of domain while preserving deterministic SHA-256 metadata.

## Artifact contract

```python
@dataclass(frozen=True, slots=True)
class MidiArtifact:
    content: bytes
    media_type: str
    file_extension: str
    size_bytes: int
    sha256: str
```

Required artifact properties:

```text
content is non-empty bytes
content begins with MThd
media_type == audio/midi
file_extension == .mid
size_bytes == len(content)
sha256 is lowercase 64-character hexadecimal
```

The artifact contains no filesystem path. Writing to disk is a caller concern.

## Export report

The immutable report records:

```text
settings
input_event_count
exported_note_count
minimum_tick_adjustment_count
zero_velocity_adjustment_count
midi_message_count
```

Required equations:

```text
input_event_count = exported_note_count
midi_message_count = 5 + 2 * exported_note_count
```

The base count of five covers two track names, one tempo message, and two end-of-track messages.

## Mido encoder and external parser validation

`MidoMidiFileEncoder` is the infrastructure adapter. It builds the file in `io.BytesIO`, saves it with Mido, then opens the resulting bytes again with a separate Mido parser pass.

The parser validates:

- file type `1`;
- division `480`;
- exactly two tracks;
- metadata track order and name;
- configured tempo;
- concert track name and end marker;
- non-negative integer deltas;
- MIDI pitch, velocity, and channel ranges;
- exact ordered note messages;
- one note-on and one note-off per plan item.

Parser or encoding failures are converted into controlled errors without leaking external exception messages as the public error text.

## Structural snapshot and temporary file

Integration tests provide two independent interoperability checks:

1. a standard-library binary snapshot verifies `MThd`, header length, type, track count, division, and both `MTrk` chunks;
2. the generated bytes are written to `tmp_path / "transcription.mid"` and opened again as a real file with Mido.

No generated MIDI is committed to the repository.

## Empty input

An empty SAX-030 result produces a valid type-one MIDI file with:

```text
metadata track
concert track
configured tempo
zero note_on messages
zero note_off messages
```

The artifact remains non-empty, parseable, deterministic, and checksummed.

## Determinism

For the same original object graph, settings, and encoder version:

```text
plan equality
byte equality
size equality
SHA-256 equality
report equality
```

Changing tempo changes timing/tempo bytes and SHA-256 while preserving source pitch and references.

## Provenance

`MidiExportResult.original` is the exact SAX-030 result. Every `MidiNotePlan.source` is the exact corresponding `WrittenPitchNoteEvent`.

The nested chain retains access to:

```text
raw TranscriptionResult
model and engine identities
engine source revision
model revision
checkpoint filename and SHA-256
inference settings
raw and postprocessed NoteEvent batches
SAX-022 settings/report
SAX-023 annotations/settings/report
concert NoteEvent
written pitch derivative
selected SaxophoneType
MIDI export settings/report/artifact
```

SAX-031 does not duplicate or rewrite provenance strings.

## Validation evidence

The integration marker is:

```text
midi_integration
```

The dedicated split contains seven real Mido tests and is required on Python 3.11, 3.12, and 3.13. Only `baseline_integration` is skipped outside Python 3.11.

Final measured core results on Python 3.13:

```text
557 passed, 1 baseline skip
7 midi_integration passed
coverage: 93.24%
Ruff lint: pass
Ruff format: pass
mypy strict: pass
```

The protected matrix also passes on Python 3.11 with the pinned FiloSax baseline and real inference.

## Architectural boundaries

SAX-031 does not change or connect:

```text
FastAPI routes
composition root
job state
repositories
persistence
workers or queues
Backend
Frontend
quality workflow structure
FiloSax contracts or checkpoint policy
```

Domain imports neither Mido nor `hashlib`. Application imports no Mido. Infrastructure owns Mido parsing and encoding.

## Limitations and later stories

Not included:

- SAX-032 tempo estimation or replacement workflow;
- SAX-033 rhythmic quantization, grid, silence notation, or overlap correction;
- SAX-034 MusicXML, measures, accidentals, or written-pitch notation;
- rendered score;
- automatic program/instrument selection;
- playback, synthesis, SoundFont, or MIDI ports;
- file persistence, object storage, download endpoint, or job association;
- multi-track instrument separation;
- Backend or Frontend integration.
