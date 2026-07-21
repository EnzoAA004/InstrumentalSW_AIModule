# TDD iteration 016 — SAX-035 SVG score rendering

## Historia y alcance

SAX-035 implementa el requisito RF-044 mediante renderizado SVG multipágina en memoria a partir de un `MusicXmlExportResult` ya construido y validado.

```text
prioridad:   P1
estimación:  5 puntos
salida:      SVG solamente
renderer:    Verovio 6.2.1
```

No genera PDF, no persiste, no utiliza rutas, no conecta FastAPI, Backend o Frontend y no inicia SAX-040 ni historias posteriores.

## Cierre de SAX-034

Antes de crear la rama se verificó PR #15:

```text
head:        544a13bb10bcfbea5cb35755ce7a34e22e10ab33
base:        300d06affc96551bb9c75d781b03bec6b795e1b2
state:       open
draft:       true
mergeable:   true
merged:      false
changed:     14 files
Quality #215 / 29840768997: Python 3.11, 3.12 y 3.13 success
```

No había comentarios, revisiones o hilos. El diff tenía exactamente los catorce archivos esperados y ningún workflow temporal. El blob protegido seguía siendo:

```text
62f8ce2737a78081a37397b1e8b7a095c00fc1b7
```

Se marcó listo y se realizó squash merge normal con `expected_head_sha`, sin auto-merge, merge commit, rebase ni bypass administrativo:

```text
3de6d26dd0e36d0d160c1fb32af8e3c0de920012
SAX-034: Export validated transposing MusicXML
```

`feature/SAX-035-svg-score-rendering` nació exactamente desde ese commit.

El conector no expone consulta directa de rulesets o branch protection. Por lo tanto, no se atribuye una inspección inexistente de esa configuración; se verificaron estado del PR, merge normal, checks y blob del workflow mediante las operaciones disponibles.

## Trazabilidad

```text
SAX-035
→ RF-044
→ ScoreRenderSettings
→ SvgPageArtifact
→ ScoreRenderResult
→ ScoreRenderer
→ VerovioSvgScoreRenderer
→ RenderMusicXmlToSvg
→ tests/unit/test_score_render_contracts.py
→ tests/unit/test_score_rendering.py
→ tests/unit/test_verovio_svg_adapter.py
→ tests/integration/test_verovio_svg_rendering.py
```

## RED

Los primeros commits agregaron únicamente builders y tests:

```text
ee6e388  add score rendering test builders
f720ac7  define SVG render contracts
00cfbf6  define revision-linked multipage rendering
fbbb1bc  define real Verovio SVG integration
```

La evidencia RED se obtuvo con un workflow temporal removido antes de producción:

```text
SAX-035 RED #1
run:      29851759615
artifact: sax035-red-evidence
ID:       8503635724
Python:   3.13.14
pytest:   9.1.1
```

Resultado exacto:

```text
collected 0 items / 3 errors
ModuleNotFoundError: No module named 'saxo_ai.domain.score_rendering'
ModuleNotFoundError: No module named 'saxo_ai.application.score_rendering'
Interrupted: 3 errors during collection
RED_EXIT_CODE=2
```

No existían módulos productivos SAX-035 en ese momento.

## GREEN

Producción mínima:

```text
9e43e68  add immutable SVG rendering contracts
c88cdeb  add revision-linked render use case
9852b75  render multipage SVG with Verovio
77c1720  register score render integration marker
```

Domain agregó settings, logs, diagnostics, artefacto por página, reporte y resultado. Application agregó DTOs del puerto, errores operativos, validación XML, SHA-256 y caso de uso. Infrastructure agregó `VerovioSvgScoreRenderer`.

## Primer diagnóstico y REFACTOR

La primera ejecución focal recolectó 94 pruebas y expuso tres expectativas de test incorrectas:

```text
provenance: dos saltos .original adicionales
architecture: valor contractual "verovio" confundido con import
integration: conteo textual de <svg demasiado restrictivo
```

También expuso formato Ruff y anotaciones mypy. El runner temporal descargable fue:

```text
SAX-035 Diagnostics #1
run:      29852273038
artifact: sax035-diagnostics
ID:       8503845796
```

El commit:

```text
3369c7d  refactor(SAX-035): canonicalize contracts tests and diagnostics
```

corrigió la cadena de procedencia, validó ausencia de `import verovio` en domain, mantuvo la verificación XML real como prueba contra concatenación, conservó logs sin recortar contenido y aplicó formato y tipos canónicos.

Luego aprobaron conjuntamente:

```text
94 SAX-035 tests
real single-page rendering
real multipage rendering
real empty-timeline rendering
Ruff lint
Ruff format
mypy strict
```

El workflow de diagnóstico fue eliminado. Ningún workflow temporal permanece en el árbol final.

## Contratos y settings

```text
policy version: 1.0
page width:     2100
page height:    2970
scale:          100
scale range:    1..1000
```

Los contratos son frozen y slotted. Se rechazan bool, float, string, `None`, cero, negativos y versiones desconocidas.

## Opciones de Verovio

```text
inputFrom:       xml
pageWidth:       settings.page_width
pageHeight:      settings.page_height
scale:           settings.scale
svgViewBox:      true
xmlIdChecksum:   true
xmlIdSeed:       absent
log buffer:      requested when exported; getLog used in pinned wheel
log level:       warning
```

Cada render crea un toolkit nuevo. La inspección del wheel 6.2.1 confirmó `enableLog` y `toolkit.getLog`, pero no `enableLogToBuffer`; no se simula una API ausente.

## Páginas y artefactos

Cada página se devuelve como documento SVG UTF-8 independiente:

```text
media type:      image/svg+xml
extension:       .svg
numbering:       1..N
compression:     none
storage:         none
```

Application analiza cada página como XML, exige root SVG con namespace, calcula tamaño y SHA-256 exactos y crea un `SvgPageArtifact`. No existe archivo concatenado, ZIP, HTML o filesystem.

## Logs

Se captura `getLog()` después de load, page count y cada página. Solo se agregan mensajes realmente producidos. Los logs conservan stage, página opcional, mensaje y orden. Los errores controlados conservan los logs existentes en un atributo separado.

## Atomicidad y aislamiento

Fallas cubiertas:

```text
loadData false o excepción
page count inválido o excepción
página uno fallida
página intermedia fallida
SVG vacío
SVG malformado
root no SVG
salida de puerto con tipo incorrecto
```

Después de cada falla permanecen intactos:

```text
MIDI bytes y SHA-256
MusicXML bytes y SHA-256
MusicXmlExportResult
QuantizedRhythmResult
TempoResolution exacta
procedencia completa
```

No se devuelve un resultado parcial.

## Integración real

La integración utiliza el encoder MusicXML real, `VerovioMusicXmlReader`, `VerovioSvgScoreRenderer` y `RenderMusicXmlToSvg`.

Casos:

```text
partitura normal con render repetido y bytes deterministas
partitura larga con page_count >= 2
timeline vacía con al menos una página válida
```

Cada página se decodifica, analiza como XML y valida por root, namespace, orden, count, tamaño y SHA. No se escribe archivo alguno.

## Arquitectura

```text
domain
  no importa XML, hashlib, Verovio, FastAPI, application o infrastructure

application
  calcula SHA-256 y valida XML
  no importa Verovio o FastAPI

infrastructure
  importa Verovio e implementa ScoreRenderer
  no crea domain artifacts ni calcula SHA-256 final
```

`main.py` y `api/routes.py` no cambian.

## Determinismo

La misma combinación de MusicXML, settings y Verovio 6.2.1 produce el mismo page count, orden, bytes, tamaños, digests y report. No se agregan timestamps, UUID, host, runner, rutas o metadata dinámica.

## Resultados finales

Los resultados completos de comandos, coverage y matriz protegida se registran en el cuerpo definitivo del PR después de validar el head limpio documentado.

## Riesgos y limitaciones

El layout es fijo por settings y depende de Verovio 6.2.1. Una partitura puede ocupar varias páginas. El baseline garantiza estructura e interoperabilidad, no calidad profesional de engraving.

No existen PDF, editor visual, reflow interactivo, playback, almacenamiento, endpoint o UI.

## Historias no implementadas

No se inició SAX-040. Tampoco se implementaron SAX-041 a SAX-045, PDF, PNG, JPEG, HTML viewer, zoom, pan, selección, highlighting, cursor, playback, MIDI sincronizado, SoundFont, edición, regeneración, metadata editable, lyrics, dynamics, articulations, slurs, ornaments, detección de tonalidad o compás, persistencia, storage, URLs firmadas, descargas, endpoint, jobs, workers, colas, entrenamiento, segundo baseline, Backend o Frontend.
