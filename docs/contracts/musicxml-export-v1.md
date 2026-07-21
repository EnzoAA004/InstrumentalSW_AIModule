# MusicXML export contract v1

## Alcance

SAX-034 consume directamente un `QuantizedRhythmResult` de SAX-033 y genera un documento MusicXML interoperable para una única parte de saxofón. No vuelve a transcribir audio, postprocesar eventos, clasificar confianza, transponer pitches, resolver tempo ni cuantizar ritmo.

La capacidad permanece interna. No se conecta con FastAPI, jobs, persistencia, Backend o Frontend y no produce render PDF o SVG.

## Trazabilidad

```text
SAX-034
→ RF-043
→ MusicXmlEncoder
→ MusicXmlReader
→ StandardLibraryMusicXmlEncoder
→ VerovioMusicXmlReader
→ ExportQuantizedRhythmToMusicXml
→ tests/unit/test_musicxml_contracts.py
→ tests/unit/test_musicxml_pitch.py
→ tests/unit/test_musicxml_measures.py
→ tests/unit/test_musicxml_export.py
→ tests/integration/test_musicxml_verovio.py
```

## Formato fijo

```text
MusicXML version:       4.0
document organization:  score-partwise
encoding:               UTF-8
compression:            none
file extension:         .musicxml
media type:             application/vnd.recordare.musicxml+xml
parts:                  1
staves:                 1
voices:                 1
clef:                   treble G2
pitch representation:   written
```

El contenido comienza con declaración XML UTF-8 y root:

```xml
<score-partwise version="4.0">
```

No se genera `.mxl`, ZIP, `META-INF` ni container XML.

## Constantes y settings

```text
MUSICXML_EXPORT_POLICY_VERSION       1.0
MUSICXML_DOCUMENT_VERSION            4.0
MUSICXML_MEDIA_TYPE                  application/vnd.recordare.musicxml+xml
MUSICXML_FILE_EXTENSION              .musicxml
MUSICXML_SCORE_TYPE                  score-partwise
MUSICXML_PITCH_REPRESENTATION        written
MUSICXML_PITCH_SPELLING_POLICY       prefer_flats
MUSICXML_DEFAULT_BEATS_PER_MEASURE   4
MUSICXML_BEAT_TYPE                   4
```

`MusicXmlExportSettings` es frozen y slotted. `beats_per_measure` acepta únicamente un `int` real positivo; rechaza booleanos, floats, strings, `None`, cero y negativos. La versión debe ser exactamente `1.0`.

El denominador permanece fijo en cuatro. La configuración permite, por ejemplo, 3/4, 4/4 y 5/4, pero no estima métrica ni implementa 6/8.

## Entrada y preservación

La entrada es exactamente:

```python
QuantizedRhythmResult
```

El exportador consume:

```python
result.tempo
result.timeline
result.report.settings.subdivisions_per_beat
```

`MusicXmlExportResult.original` conserva por identidad el resultado usado. Permanecen accesibles la revisión y fuente de tempo, estimate automático opcional, BPM manual, transcripción cruda, modelo, revisiones de origen, checkpoint, settings de inferencia, reportes SAX-022/SAX-023, confidence, baja confianza, pitch de concierto, pitch escrito y reporte de cuantización.

SAX-033 no se vuelve a ejecutar y su timeline no se modifica.

## Pitch escrito y spelling

Cada nota utiliza:

```python
quantized_note.source.written_pitch_midi
```

El pitch de concierto permanece solo en la cadena de procedencia. La política fija `prefer_flats` utiliza:

```text
0 C
1 D-flat
2 D
3 E-flat
4 E
5 F
6 G-flat
7 G
8 A-flat
9 A
10 B-flat
11 B
```

Los bemoles se representan mediante `step` diatónico y `alter = -1`. `alter` se omite cuando vale cero.

```text
octave = written_pitch_midi // 12 - 1
```

No existe inferencia de tonalidad, key signature, enharmonía contextual, dobles alteraciones ni accidentales de cortesía.

## Instrumentos y transposición

```text
SOPRANO   Soprano Saxophone in B-flat   diatonic -1  chromatic -2  total -2
ALTO      Alto Saxophone in E-flat      diatonic -5  chromatic -9  total -9
TENOR     Tenor Saxophone in B-flat     diatonic -1  chromatic -2  octave -1  total -14
BARITONE  Baritone Saxophone in E-flat  diatonic -5  chromatic -9  octave -1  total -21
```

El total se calcula como:

```text
chromatic + 12 × octave_change
```

Un `octave_change` ausente equivale a cero. El contrato exige que el total sea exactamente el negativo del offset escrito de SAX-030. Para alto, concert MIDI 60 se conserva en procedencia, written MIDI 69 se escribe como A4 y `<transpose>` informa -9 semitonos written → sounding.

## Divisions y compases

```text
divisions = result.report.settings.subdivisions_per_beat
measure_capacity_divisions = beats_per_measure × divisions
```

Cada paso SAX-033 equivale a una unidad MusicXML de `<duration>`. No se convierte a ticks MIDI ni se utiliza 480.

La timeline se recorre en orden y cada item `[start_step, end_step)` se segmenta en fronteras de compás. Los compases se numeran desde uno. Todos los segmentos tienen duración positiva y quedan dentro de un único compás.

Todo compás anterior al último suma exactamente su capacidad. El último compás puede ser parcial; no se agrega un silencio final para completarlo.

Una timeline vacía produce una parte y un compás número uno con attributes y dirección de tempo, sin `<note>` ni duración inventada.

## Notas, silencios y ties

Cada segmento de nota contiene pitch escrito, duration, voice uno y staff uno. No se agregan `type`, `dot`, `time-modification`, `beam`, `stem` ni `accidental`.

Cada segmento de `QuantizedRest` contiene `rest`, duration, voice uno y staff uno. Los silencios que cruzan una frontera se segmentan sin ties. No se crean rests ausentes de la timeline.

Una nota segmentada por barlines conserva el mismo `QuantizedNoteEvent` fuente:

```text
segmento único:      sin tie
primer segmento:    start
intermedio:          stop + start
último segmento:    stop
```

Se emiten tanto `<tie>` como `<notations><tied>`. No se unen dos notas originales distintas aunque compartan pitch y sean adyacentes. No se implementan slurs.

## Primer compás

Antes de notas y silencios aparecen:

```text
attributes/divisions
attributes/time/beats
attributes/time/beat-type
attributes/clef/sign G
attributes/clef/line 2
attributes/transpose
```

Luego se emite una dirección de metrónomo negra y `<sound tempo>` usando exclusivamente `result.tempo.effective_tempo_bpm`. El BPM se representa de manera determinista, decimal y sin notación científica.

## Estructura del score

La estructura estable contiene título `Saxo Transcription`, una única entrada `score-part` con id `P1`, un `score-instrument` con id `P1-I1`, una única parte `P1` y compases numerados.

No incluye compositor, copyright, fecha, timestamp, UUID, rutas, modelo, checkpoint, confidence o información privada.

## Contratos

Domain define contratos frozen y slotted para settings, instrumento, resumen de validación, artefacto, reporte y resultado. Domain no importa XML, ElementTree, Verovio, hashlib ni FastAPI.

Application define los puertos runtime-checkable:

```python
MusicXmlEncoder.encode(...) -> bytes
MusicXmlReader.validate(...) -> MusicXmlValidationSummary
```

Los puertos reciben memoria, no paths ni storage. Application planifica segmentos y compases, resuelve instrumento y spelling, calcula SHA-256 exacto y valida consistencia entre encoder, reader y reporte. Application no importa Verovio.

Infrastructure contiene `StandardLibraryMusicXmlEncoder`, basado en `xml.etree.ElementTree`, y `VerovioMusicXmlReader`. Generación y validación externa permanecen en clases diferentes.

## Artefacto y hashing

`MusicXmlArtifact` contiene bytes, media type, extensión, tamaño y SHA-256. No contiene path y no se persiste.

Domain valida UTF-8, declaración XML, root/version, metadata, longitud y forma hexadecimal minúscula del digest. Application calcula:

```python
sha256(content).hexdigest()
```

La misma entrada y settings producen bytes, tamaño, digest, reporte y validación equivalentes.

## Verovio

La dependencia normal está fijada a `verovio==6.2.1`. `VerovioMusicXmlReader` decodifica UTF-8, configura input MusicXML, ejecuta `loadData`, exige éxito y comprueba una representación MEI no vacía. Los tests también escriben `transcription.musicxml` en `tmp_path` y lo cargan desde disco.

El log externo se limita a un resumen saneado en errores controlados. Nunca se incluye el documento completo, eventos, modelo, checkpoint, rutas o stack trace.

No se llama a renderizado SVG ni PDF.

## Reporte

El reporte distingue fuentes originales de segmentos:

```text
source_note_count
source_rest_count
measure_count
note_segment_count
rest_segment_count
split_note_count
split_rest_count
final_measure_used_divisions
measure_capacity_divisions
```

`split_note_count` y `split_rest_count` cuentan items originales que generan más de un segmento. La validación externa debe informar una parte y conteos iguales al reporte.

## Determinismo y complejidad

No se usan fecha, hora, UUID, variables de entorno, versión de Python ni información del runner.

```text
segmentación: O(n + s)
encoding:     O(n + s)
memoria:      O(n + s)
validación:   dependiente de Verovio
```

`s` representa segmentos adicionales creados por barlines.

## Limitaciones

La política usa métrica manual con negra como beat y no conoce tonalidad, cambios de compás, articulaciones, dynamics, lyrics, beams, tuplets notados, ornaments o layout. MusicXML conserva duración por divisions, pero no inventa símbolos gráficos para rejillas ternarias o duraciones compuestas.

SAX-035 no está implementada. No existe PDF, SVG, render, layout de páginas, selección de fuente musical, playback o SoundFont.
