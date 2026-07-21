# TDD iteration 013 — SAX-032 tempo resolution

## Historia y alcance

SAX-032 resuelve tempo automático o manual para `WrittenPitchTranscriptionResult` y regenera MIDI mediante SAX-031. No implementa cuantización, análisis de audio, FastAPI, jobs, persistencia, Backend o Frontend.

## Cierre de SAX-031

PR #12 fue verificado en `2e8dfad608136e79d538efef9303083ffcbf6e0a`, sin comentarios, revisiones o hilos. Quality #161 (`29790875451`) pasó en Python 3.11/3.12/3.13. Se marcó listo y se realizó squash merge normal:

```text
fa78890a7025c2f6342cabdbfab49816823cbd69
SAX-031: Export validated concert-pitch MIDI
```

No se usó auto-merge ni bypass. La rama SAX-032 nació exactamente desde ese commit.

## Trazabilidad

```text
SAX-032
→ TempoEstimator
→ OnsetIntervalTempoEstimator
→ EstimateTranscriptionTempo
→ ConfigureManualTempo
→ OverrideEstimatedTempo
→ ExportTempoResolvedMidi
→ tests/unit/test_tempo_contracts.py
→ tests/unit/test_tempo_estimation.py
→ tests/unit/test_tempo_resolution.py
→ tests/integration/test_tempo_midi_regeneration.py
```

## RED

Commits solo de tests:

```text
8dbf070  define tempo estimation and override contracts
02e290a  define deterministic onset tempo estimator
cd747ed  define manual tempo resolution revisions
ca8dab2  define tempo-dependent MIDI regeneration
```

Resultado exacto, Python 3.13.5:

```text
4 errors during collection
missing saxo_ai.domain.tempo
missing saxo_ai.application.tempo_resolution
missing saxo_ai.infrastructure.onset_interval_tempo
collected 0 items
RED_EXIT_CODE=2
```

## GREEN

Producción mínima:

```text
9dc8ffb  add immutable tempo resolution contracts
3ef76e3  support automatic manual and override tempo resolution
4a84d0f  estimate tempo from onset intervals
```

Se agregaron settings, estimate, source enum, resolution, errores, puerto, estimador IOI, selección automática/manual, override y regeneración MIDI.

GREEN focal inicial:

```text
87 passed
```

## Casos y fórmulas

```text
0.0, 0.5, 1.0, 1.5 → 120 BPM, 3/3 inliers
0.0, 1.0, 2.0, 3.0 → 60 BPM
60/120/240 candidates → consenso de octava
outlier temporal → 3/4 inliers, confidence 0.75
```

```text
raw_bpm = 60.0 / interval_seconds
confidence = inliers / intervals
relative_error = abs(equivalent - estimate) / estimate
```

También se probaron onsets repetidos, material insuficiente, rango sin equivalencia, manual directo, overrides repetidos y preservación completa.

Confidence expresa consistencia interna; `0.8` no significa 80 % de exactitud.

## Regeneración MIDI

La integración prueba:

1. estimación automática a 120 BPM;
2. exportación MIDI;
3. override manual a 60 BPM;
4. nueva exportación;
5. revisiones 1 y 2;
6. metaeventos 500000 y 1000000;
7. ticks, bytes y SHA diferentes;
8. procedencia original intacta.

Concert pitch, written pitch, baja confianza, modelo, checkpoint y settings se conservan.

## REFACTOR

```text
e4637e5  centralize octave-equivalent tempo consensus
458ec9d  apply canonical onset estimator formatting
da5b611  share BPM validation with MIDI settings
```

Se centralizaron validación BPM, equivalencias y fórmula de confidence. Se usa `pairwise`. SAX-031 conserva su chequeo adicional de tempo MIDI representable.

Bloque focal final:

```text
92 passed
Ruff lint passed
Ruff format passed on 7 files
```

## Quality #163

Run `29793983718` falló dentro del gate después de instalar correctamente.

La causa reproducida estaba en una nueva prueba: consideraba `1.0 BPM` válido y usaba el recíproco del límite MIDI. SAX-031 ya rechazaba correctamente ese valor.

Corrección:

```text
válido: 60_000_000 / 16_777_215
inválido: 1.0
d1d7fff  correct MIDI representable BPM regression
```

Producción no cambió por este fallo.

## Quality #164

Run `29794352158` detectó que el test corregido no coincidía con Ruff format.

```text
8eabdde  apply canonical BPM regression formatting
```

## Matriz funcional

Quality #165, run `29794496404`:

```text
Python 3.11 — success
Python 3.12 — success
Python 3.13 — success
```

Python 3.11 completó FFmpeg, instalador fijado, PEP 610, checkpoint, inferencia CPU real, MIDI integration y gate completo. Python 3.12/3.13 ejecutaron núcleo, FFmpeg, MIDI integration y gate completo, omitiendo solo el baseline real.

## Comandos y marker splits

La cola del log protegido se truncó antes del resumen. Se creó una verificación temporal descargable:

```text
run: 29794839849
artifact: sax032-command-metrics
artifact ID: 8481634315
```

Resultados funcionales:

```text
pytest:               650 passed, 1 skipped
not integration:      632 passed, 19 deselected
integration:           18 passed, 1 skipped, 632 deselected
midi_integration:       9 passed, 642 deselected
baseline_integration:   1 skipped, 650 deselected
```

El único fallo del job temporal fue Ruff sobre su propio script no formateado. Workflow y script fueron eliminados:

```text
eb09ffe  remove temporary command metrics workflow
9ffed02  remove temporary command metrics runner
```

No queda diagnóstico en el árbol final.

## Cobertura y herramientas

```text
1954 statements
108 missed
586 branches
74 partial branches
92.60 % total
required: 90.00 %
```

```text
application/tempo_resolution.py         83 %
domain/tempo.py                         96 %
infrastructure/onset_interval_tempo.py  82 %
```

No se redujo el umbral ni se excluyeron módulos.

Sobre el head funcional limpio:

```text
Ruff lint:   passed
Ruff format: 87 files already formatted
mypy:        no issues in 87 source files
```

## Limitación local

El sandbox no tiene `gh` y no resuelve `github.com` para un clone normal. Las pruebas focales se ejecutaron en un workspace reconstruido; instalación integral, cobertura y matriz se acreditan mediante GitHub Actions.

## Preservación y exclusiones

No cambiaron `NoteEvent`, SAX-022/023/030, MIDI type 1, 480 ticks, tracks, channel, concert pitch, velocity, ordering, baseline runtime, workflow protegido, FastAPI o `main.py`.

No se comenzó SAX-033. No hay notas cuantizadas, rejillas, figuras, silencios, compás, MusicXML, partitura, beat tracking de audio, reproducción, persistencia, endpoint, worker, cola, Backend o Frontend.
