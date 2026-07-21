# Score rendering contract v1

## Alcance

SAX-035 consume un `MusicXmlExportResult` ya construido y validado por SAX-034 y produce páginas SVG independientes en memoria. No vuelve a cuantizar, resolver tempo, transponer, generar MusicXML, ejecutar el modelo ni leer audio.

La capacidad permanece interna. No se conecta con FastAPI, jobs, persistencia, Backend o Frontend. Esta versión no genera PDF y no inicia SAX-040 ni historias posteriores.

## Trazabilidad

```text
SAX-035
→ RF-044
→ ScoreRenderer
→ VerovioSvgScoreRenderer
→ RenderMusicXmlToSvg
→ tests/unit/test_score_render_contracts.py
→ tests/unit/test_score_rendering.py
→ tests/unit/test_verovio_svg_adapter.py
→ tests/integration/test_verovio_svg_rendering.py
```

## Entrada y relación de procedencia

La entrada exacta es:

```python
MusicXmlExportResult
```

El resultado conserva identidad:

```python
score_render_result.original is musicxml_export_result_used
```

Por esa referencia permanecen accesibles:

```text
ScoreRenderResult
→ MusicXmlExportResult
→ QuantizedRhythmResult
→ TempoResolution exacta
→ WrittenPitchTranscriptionResult
→ ConfidenceAnnotatedTranscriptionResult
→ PostProcessedTranscriptionResult
→ TranscriptionResult
→ model identity, source/model revisions y checkpoint SHA-256
→ NoteEventBatch
```

No se crea una nueva revisión de MusicXML, ritmo o tempo. `source_tempo_revision` se copia de la revisión exacta ya asociada al MusicXML.

## Formato fijo

```text
encoding:          UTF-8
media type:        image/svg+xml
file extension:    .svg
compression:       none
organization:      one artifact per page
page numbering:    1-based
storage:           none
renderer:          verovio
renderer version:  6.2.1
```

Cada página es un documento XML independiente con root local-name `svg` y namespace:

```text
http://www.w3.org/2000/svg
```

No se concatena más de un root `<svg>`, no se crea ZIP, HTML, PDF, PNG o JPEG y no se escribe ninguna ruta.

## Settings

```text
SCORE_RENDER_POLICY_VERSION       1.0
page_width                        2100
page_height                       2970
scale                             100
minimum scale                     1
maximum scale                     1000
```

`ScoreRenderSettings` es frozen y slotted. `page_width` y `page_height` aceptan únicamente `int` reales positivos. `scale` acepta un `int` real entre 1 y 1000 inclusive. Se rechazan booleanos, floats, strings, `None`, cero, negativos y versiones desconocidas. No existen variables de entorno para estos valores.

## Opciones deterministas de Verovio

Cada operación crea una instancia nueva del toolkit y aplica explícitamente:

```python
{
    "inputFrom": "xml",
    "pageWidth": settings.page_width,
    "pageHeight": settings.page_height,
    "scale": settings.scale,
    "svgViewBox": True,
    "xmlIdChecksum": True,
}
```

Para SVG no se configura `xmlIdSeed`. Los identificadores se derivan del contenido mediante `xmlIdChecksum`. El renderer fija `LOG_WARNING`. La referencia de Verovio documenta `enableLogToBuffer`, pero el wheel Python fijado 6.2.1 no exporta esa función; el adaptador la invoca cuando el binding la ofrece y, en el wheel validado, consume el buffer disponible directamente mediante `toolkit.getLog()`.

## Render multipágina

`VerovioSvgScoreRenderer`:

1. valida bytes no vacíos;
2. decodifica MusicXML como UTF-8;
3. crea un toolkit nuevo;
4. solicita buffer cuando la función está exportada y fija warning logs;
5. configura las opciones fijas;
6. ejecuta `loadData`;
7. exige carga exitosa;
8. obtiene `getPageCount()`;
9. exige un entero real positivo;
10. recorre `1..page_count` en orden;
11. llama `renderToSVG(page_number, True)`;
12. codifica cada string SVG como UTF-8;
13. devuelve todas las páginas o falla atómicamente.

No utiliza `renderToSVGFile`, `tempfile`, `Path` ni filesystem. Una página intermedia fallida impide devolver cualquier resultado exitoso parcial.

## Logs de herramienta

El adaptador captura `getLog()` después de:

```text
loadData
getPageCount
cada renderToSVG
```

Los mensajes nuevos se conservan con su contenido y orden. Una operación sin mensaje no inventa una entrada.

```python
ScoreRenderLogEntry(
    stage="load" | "page_count" | "render_page",
    page_number=None | positive_int,
    message=tool_message,
)
```

`page_number` es `None` en `load` y `page_count`; es positivo en `render_page`. Los logs exitosos quedan en `ScoreRenderDiagnostics`. Al fallar, los logs capturados hasta ese punto quedan disponibles en el error controlado mediante un atributo separado. No se concatenan al mensaje público.

Los logs no participan del SHA-256 de las páginas.

## Contratos de dominio

Domain define contratos frozen y slotted:

```text
ScoreRenderSettings
ScoreRenderLogEntry
ScoreRenderDiagnostics
SvgPageArtifact
ScoreRenderReport
ScoreRenderResult
```

Domain no importa `hashlib`, parser XML, Verovio, FastAPI, application o infrastructure.

## Artefacto de página

`SvgPageArtifact` contiene:

```text
page_number
page_count
content
media_type
file_extension
size_bytes
sha256
```

Invariantes:

```text
1 <= page_number <= page_count
page_count > 0
content: bytes UTF-8 no vacíos
XML bien formado validado en application
root local-name: svg
namespace SVG explícito
media_type: image/svg+xml
file_extension: .svg
size_bytes == len(content)
sha256: 64 caracteres hex lowercase
```

Domain valida la forma estructural y hexadecimal, pero no calcula el digest. Application calcula exactamente:

```python
sha256(content).hexdigest()
```

No se almacena path, URL, nombre de archivo físico ni información del host.

## Reporte

`ScoreRenderReport` contiene:

```text
settings
page_count
total_size_bytes
source_musicxml_sha256
source_tempo_revision
```

El resultado valida:

```text
page_count == len(pages)
total_size_bytes == sum(page.size_bytes)
source_musicxml_sha256 == original.artifact.sha256
source_tempo_revision == original.original.tempo.revision
```

Las páginas deben aparecer exactamente en el orden `1..N` y cada `page_count` debe ser `N`.

## Puerto de application

```python
@runtime_checkable
class ScoreRenderer(Protocol):
    def render(
        self,
        *,
        content: bytes,
        settings: ScoreRenderSettings,
    ) -> ScoreRendererOutput:
        ...
```

El puerto trabaja únicamente con memoria. No recibe paths, storage, jobs ni transportes. Devuelve DTOs crudos de páginas ordenadas y logs; no conoce contratos de artefacto final y no calcula digests.

## Caso de uso

`RenderMusicXmlToSvg`:

1. valida `MusicXmlExportResult` y settings;
2. invoca el renderer una sola vez;
3. valida tipo, tuple, orden y contenido de la salida;
4. analiza cada SVG como XML en application;
5. verifica root y namespace;
6. calcula SHA-256 exacto;
7. construye todos los artifacts;
8. construye diagnostics y report;
9. conserva el original por identidad;
10. devuelve un resultado atómico.

No importa Verovio y no llama al encoder/reader MusicXML, cuantizador, estimador de tempo, encoder MIDI o motor de transcripción.

## Errores y atomicidad

Errores de contrato:

```text
InvalidScoreRenderSettingsError
InvalidScoreRenderLogEntryError
InvalidScoreRenderDiagnosticsError
InvalidSvgPageArtifactError
InvalidScoreRenderReportError
InvalidScoreRenderResultError
InvalidScoreRendererOutputError
```

Errores operativos:

```text
ScoreRenderingError
ScoreRendererLoadError
ScorePageCountError
ScorePageRenderingError
```

Los errores operativos conservan:

```text
stage
page_number cuando corresponde
logs capturados
__cause__ para excepciones inesperadas
```

Los mensajes públicos son estables y no incluyen MusicXML, SVG, audio, modelo, checkpoint, rutas, stack trace o logs completos.

Una falla de render no modifica:

```text
MIDI bytes o SHA-256 ya generados
MusicXML bytes o SHA-256
MusicXmlExportResult
QuantizedRhythmResult
TempoResolution
transcripción o procedencia
```

No se devuelve `ScoreRenderResult` parcial y no se eliminan artefactos anteriores.

## Determinismo

Para la misma combinación:

```text
MusicXmlExportResult
ScoreRenderSettings
Verovio 6.2.1
```

se exige igualdad de:

```text
page_count
orden
bytes SVG por página
tamaño por página
SHA-256 por página
report
```

Los contratos propios no agregan fecha, hora, UUID, runner, hostname, ruta, directorio temporal, versión de Python o sistema operativo.

## Timeline vacía

Un MusicXML válido proveniente de una timeline vacía puede renderizar al menos una página SVG válida. SAX-035 no inventa notas o silencios y no altera el MusicXML. No se establece una expectativa visual específica para esa página.

## Arquitectura

```text
domain
  importa MusicXmlExportResult como contrato fuente
  no importa application, infrastructure, XML, hashlib, Verovio o FastAPI

application
  importa domain
  puede importar hashlib y parser XML
  no importa Verovio o FastAPI

infrastructure
  implementa ScoreRenderer
  importa Verovio
  no calcula SHA-256 final ni crea domain artifacts
```

`main.py` y `api/routes.py` no registran el caso de uso.

## Limitaciones

El baseline utiliza layout fijo por settings y puede producir una o varias páginas. La distribución depende de Verovio 6.2.1. La validación garantiza estructura, procedencia y reproducibilidad del artefacto, no calidad profesional de engraving.

Todavía no existen edición visual, reflow interactivo, highlighting, cursor, playback, PDF, persistencia, almacenamiento, endpoint o integración UI.

## Historias futuras

SAX-035 no inicia SAX-040 ni ninguna historia posterior. PDF, visualización web/móvil, descarga, almacenamiento y edición quedan fuera de esta versión.
