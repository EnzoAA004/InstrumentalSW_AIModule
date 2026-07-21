# TDD iteration 015 — SAX-034 MusicXML export

## Historia y alcance

SAX-034 genera MusicXML 4.0 interoperable desde `QuantizedRhythmResult`. La historia incluye instrumento, transposición, compases, notas, silencios, ties de barline, tempo, artefacto determinista y validación externa con Verovio.

No implementa SAX-035, SVG, PDF, rendering, FastAPI, jobs, persistencia, Backend o Frontend.

## Cierre de SAX-033

Antes de iniciar esta rama se verificó PR #14:

```text
state:       open
draft:       true
mergeable:   true
merged:      false
head:        05ede2491f2884b233ea0541178226c4cf2f8fa9
changed:     9 files
Quality #186 / 29835133058: 3.11, 3.12, 3.13 success
```

No había comentarios, revisiones o hilos. El diff no contenía API, infraestructura o workflows y el blob protegido seguía siendo `62f8ce2737a78081a37397b1e8b7a095c00fc1b7`.

Se marcó listo y se realizó squash merge normal, sin auto-merge ni bypass:

```text
300d06affc96551bb9c75d781b03bec6b795e1b2
SAX-033: Quantize monophonic rhythm and rests
```

`feature/SAX-034-musicxml-export` nació exactamente desde ese commit.

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

## RED

Los commits de RED agregaron exclusivamente builders y pruebas:

```text
a1c6b5d  add MusicXML test builders
cf17b20  define MusicXML export contracts
e43aa07  define written pitch spelling
582829b  define measure and transposition structure
c09588d  define artifact validation and preservation
c77c391  define external MusicXML validation
```

La ejecución descargable utilizó un workflow temporal, removido antes de producción:

```text
SAX-034 RED #2
run:      29838086400
artifact: sax034-red-evidence
ID:       8498155269
Python:   3.13.14
```

Resultado exacto:

```text
collected 0 items / 4 errors
ModuleNotFoundError: No module named 'saxo_ai.application.musicxml_export'
Interrupted: 4 errors during collection
RED_EXIT_CODE=2
```

Los cuatro archivos unitarios fallaron durante collection por ausencia de módulos SAX-034, antes de cualquier implementación productiva.

## GREEN

Producción mínima:

```text
5f3aaab  add MusicXML artifact contracts
cf1f625  plan measures and export MusicXML artifacts
eed1a17  encode score-partwise MusicXML
5e6c55e  validate MusicXML with Verovio
6417aec  pin Verovio and register integration marker
```

El dominio agregó settings, instrumento, summary, artefacto, reporte y resultado. Application agregó puertos, spelling, specs, segmentación, plan de compases, SHA-256 y caso de uso. Infrastructure agregó encoder ElementTree y reader Verovio.

## Correcciones reveladas por el primer quality gate

La primera matriz instaló Verovio y llegó a pytest, pero expuso defectos de integración y controles:

```text
pytest: marker múltiple incompatible con pytest 9
Ruff:  dos zip() sin strict
format: cinco archivos no canónicos
mypy:  frontera Verovio, retorno ElementTree y helper sin tipo
```

Un runner focal descargable separó los resultados:

```text
SAX-034 Diagnostics #1
run:      29838883331
artifact: sax034-diagnostics
ID:       8498484111
```

Se corrigieron markers como lista, `zip(..., strict=True)`, typing de Verovio y bytes XML, anotaciones de helpers y formato Ruff. El runner creó:

```text
c8b0efd  refactor(SAX-034): apply canonical typing and formatting
```

Luego aprobó conjuntamente:

```text
89 SAX-034 tests
Ruff lint
Ruff format
mypy strict
```

Los workflows temporales RED y diagnóstico fueron eliminados. No permanecen en el árbol final.

## Pitch cases

La política `prefer_flats` cubre los doce pitch classes y los límites:

```text
MIDI 0   C-1
MIDI 60  C4
MIDI 61  D-flat4
MIDI 69  A4
MIDI 127 G9
```

El caso alto conserva concert MIDI 60 en procedencia, escribe written MIDI 69 como A4 y declara transposición total -9.

## Instrument cases

```text
Soprano   -2
Alto      -9
Tenor    -14
Baritone -21
```

Cada total es el negativo del offset escrito SAX-030.

## Measure cases

Se cubrieron 3/4, 4/4 y 5/4 settings; grids SAX-033 como divisions; un compás; tres compases; compases anteriores completos; último parcial sin fill; timeline vacía; rests iniciales e internos; rest cruzando barline; nota cruzando uno o más barlines.

## Ties

```text
single:       none
first:        start
middle:       stop + start
last:         stop
```

Se validan `<tie>` y `<notations><tied>`. Rests no reciben ties y dos notas originales diferentes nunca se unen.

## External reader

`VerovioMusicXmlReader` configura input XML, carga bytes con `loadData`, exige MEI no vacío y resume conteos. La integración escribe:

```text
tmp_path / "transcription.musicxml"
```

El mismo contenido se vuelve a cargar con `loadFile`. No se llama a rendering SVG o PDF.

## Arquitectura

- domain no importa XML, ElementTree, Verovio, hashlib o FastAPI;
- application calcula SHA-256 y no importa Verovio;
- ElementTree y Verovio permanecen en infrastructure;
- puertos reciben bytes, no paths ni storage;
- routes y composition root no cambian;
- workflow protegido y baseline no cambian;
- SAX-033 no cambia funcionalmente.

## Determinismo y complejidad

Misma entrada y settings producen bytes, tamaño, digest y reporte idénticos. No existen timestamps, UUID o metadata dinámica.

```text
segmentación: O(n + s)
encoding:     O(n + s)
memoria:      O(n + s)
reader:       dependiente de Verovio
```

## Resultados finales

Los resultados completos, marker splits, cobertura, Ruff, formato, mypy y matriz protegida se registrarán en el cuerpo definitivo del PR después de validar el head documentado y limpio.

## Historias no implementadas

No se inició SAX-035. No existe SVG, PDF, render, layout, fuente musical, score multiparte, métrica automática, cambios de compás, tonalidad, key signature, enharmonía contextual, lyrics, articulaciones, dynamics, slurs, beams, tuplets notados, ornaments, playback, SoundFont, persistencia, storage, endpoint, worker, cola, entrenamiento, segundo baseline, Backend o Frontend.
