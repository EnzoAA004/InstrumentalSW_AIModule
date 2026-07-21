# TDD iteration 014 — SAX-033 monophonic rhythm quantization

## Historia y alcance

SAX-033 cuantiza `TempoResolution.original.events` sobre una rejilla uniforme configurable, resuelve una línea monofónica sin eliminar notas, genera silencios positivos explícitos, informa diferencias de timing y conserva la revisión exacta de tempo y todas las referencias fuente.

No implementa SAX-034, compases, indicación de compás, armadura, nombres de notas, figuras, tuplets escritos, MusicXML, partitura, renderizado, reproducción, FastAPI, jobs, persistencia, Backend o Frontend.

## Verificación de SAX-032

Antes de crear la rama se verificó:

```text
PR #13: closed / merged
head: d85a2315d66ef52f963d1d3a5e81419fd7d61544
squash en main: 5a9b45f96803f78b2289f371a290f9fc8d79a2f8
Quality #172: Python 3.11 / 3.12 / 3.13 success
```

`main` apuntaba al squash y `quality.yml` conservaba la matriz protegida sin workflows temporales. La rama `feature/SAX-033-monophonic-rhythm-quantization` nació exactamente desde ese commit. SAX-032 no fue modificada funcionalmente.

## Trazabilidad

```text
SAX-033
→ RhythmQuantizationSettings
→ QuantizedNoteEvent
→ QuantizedRest
→ QuantizedRhythmResult
→ QuantizeMonophonicRhythm
→ tests/unit/test_rhythm_quantization_contracts.py
→ tests/unit/test_rhythm_quantization.py
→ tests/unit/test_rhythm_quantization_timeline.py
→ tests/integration/test_rhythm_tempo_revision.py
```

No se creó un identificador RF nuevo.

## RED

Commits solo de tests, publicados antes de producción:

```text
d99e18e test(SAX-033): define rhythm quantization contracts
a78eebb test(SAX-033): define grid and overlap behavior
1dc0f99 test(SAX-033): define monophonic rests and timeline invariants
16bdc9e test(SAX-033): define tempo-revision regeneration
7943fe3 test(SAX-033): compare tempo-dependent note boundaries
```

El último commit corrige una expectativa de prueba: al reducir 120 BPM a 60 BPM un onset particular seguía redondeando al paso 1, aunque el offset, los deltas y el timeline sí cambiaban. El criterio requiere que cambien pasos **o** deltas; la prueba pasó a comparar ambas fronteras. La corrección continuó siendo anterior al código de producción.

Resultado RED reproducido en Python 3.13.5:

```text
collected 0 items / 4 errors
ModuleNotFoundError: saxo_ai.domain.rhythm_quantization
ModuleNotFoundError: saxo_ai.application.rhythm_quantization
Interrupted: 4 errors during collection
RED_EXIT_CODE=2
```

Quality #174 (`29833217220`) confirmó el mismo estado RED en la matriz protegida: los tres jobs llegaron al quality gate y fallaron por los módulos SAX-033 ausentes, no por instalación, workflow o baseline.

## GREEN

Producción mínima:

```text
f24e380 feat(SAX-033): add immutable rhythm contracts
8812579 feat(SAX-033): quantize timing and resolve monophonic overlaps
```

Se agregaron exclusivamente:

- settings frozen/slotted;
- redondeo decimal half-up centralizado;
- segundos ↔ pasos centralizados;
- candidatos con duración mínima de un paso;
- orden temporal sobre una copia de referencias;
- política monofónica de truncado o desplazamiento;
- notas cuantizadas y silencios inmutables;
- timeline contigua validada;
- deltas firmados y métricas agregadas;
- caso de uso sin puerto ni infraestructura.

GREEN focal en workspace reconstruido:

```text
71 passed
```

El workspace local no pudo clonar GitHub por resolución DNS. Se reconstruyó únicamente el paquete focal y se usaron GitHub Actions como evidencia integral del repositorio real. No se inventaron resultados del repositorio completo.

## Rejilla y redondeo

Defaults:

```text
policy_version:          1.0
subdivisions_per_beat:     4
rounding:                 nearest_half_up
overlap:                  truncate_earlier_then_shift_same_step
rests:                    explicit_positive_grid_gaps
```

Fórmulas:

```text
beat_position = seconds × effective_tempo_bpm / 60
grid_position = beat_position × subdivisions_per_beat
seconds_per_step = 60 / effective_tempo_bpm / subdivisions_per_beat
quantized_seconds = grid_step × seconds_per_step
```

`Decimal(str(value))` y `ROUND_HALF_UP` cubren explícitamente `0.49`, `0.50`, `1.49` y `1.50`. Se probaron rejillas `2`, `3`, `4` y `8`, además del caso exacto 120 BPM / cuatro subdivisiones, donde `0.125..0.500 s` produce `[1, 4)`.

## Duración mínima, orden y overlaps

Cada onset y offset se redondea por separado. Si el offset candidato no supera al onset, se usa `onset + 1` y se incrementa `minimum_duration_adjustment_count`.

La entrada puede estar desordenada. Se ordena una copia por onset original, offset original, pitch de concierto y `source_index`; `TempoResolution.original.events` conserva orden, tupla e identidades.

Política:

```text
current_onset >= previous_offset
→ sin ajuste

previous_onset < current_onset < previous_offset
→ previous_offset = current_onset

current_onset <= previous_onset
→ current_onset = previous_offset
→ current_offset = max(current_offset, current_onset + 1)
```

Se probaron truncado normal, colisión en el mismo paso, cadenas de cuatro eventos, mismo pitch y pitch diferente. Ninguna nota se elimina, fusiona o prioriza por confidence.

## Rests y timeline

Se probaron:

- silencio inicial;
- silencio interno;
- notas adyacentes sin rest;
- gap real que colapsa sin rest cero;
- ausencia de silencio final;
- lote vacío sin duración inventada.

`QuantizedRhythmResult` valida comienzo en cero, duración positiva, continuidad, ausencia de overlaps, ausencia de huecos no representados, ausencia de rests consecutivos/finales y cobertura exacta de cada índice y referencia original.

## Deltas y reporte

Los deltas definitivos se calculan después de duración mínima y overlaps:

```text
onset_delta = quantized_onset_seconds - original_onset_seconds
offset_delta = quantized_offset_seconds - original_offset_seconds
```

Las pruebas cubren adelanto, retraso, frontera exacta y corrección por overlap. El reporte valida conteos, suma absoluta de onsets, suma absoluta de offsets y máximo error absoluto de frontera. Lote vacío produce métricas `0.0`.

## Revisión de tempo y preservación

La integración crea una resolución manual a 120 BPM, cuantiza, crea override a 60 BPM y vuelve a cuantizar. Confirma:

```text
first.tempo is first_resolution
second.tempo is overridden_resolution
first.tempo.revision == 1
second.tempo.revision == 2
```

El primer resultado permanece intacto, las fronteras o deltas cambian con el nuevo BPM y ambos resultados conservan exactamente las mismas referencias fuente. También permanecen idénticos confidence `0.0/1.0`, baja confianza verdadera/falsa, pitch de concierto, pitch escrito, velocity, modelo, checkpoint y reportes anteriores.

## REFACTOR

Se centralizaron:

- redondeo;
- conversiones de rejilla;
- creación de candidatos;
- política de overlap;
- finalización de deltas;
- generación de timeline;
- cálculo de reporte;
- validación integral de timeline.

Se reemplazaron recorridos de pares por `itertools.pairwise`, se agregaron tipos de retorno explícitos y se aplicó Ruff 0.15.22. La complejidad final es `O(n log n)` tiempo por ordenamiento y `O(n)` memoria.

## Comandos completos

Para obtener resultados exactos pese al bloqueo local se ejecutó un runner temporal descargable en GitHub Actions:

```text
workflow: SAX-033 Metrics #1
run: 29834812334
artifact: sax033-command-metrics
artifact ID: 8496848536
head: 672c9956627273efaf53b4d06f8fd55c53673a00
```

El workflow temporal se eliminó inmediatamente después de recolectar la evidencia:

```text
1bf18cc chore(SAX-033): remove temporary metrics workflow
```

No queda workflow, script, flag o ruta diagnóstica en el árbol final.

Resultados Python 3.13.14:

```text
python scripts/check_quality.py
→ 721 passed, 1 skipped
→ 2243 statements, 129 missed
→ 686 branches, 91 partial branches
→ 92.28% coverage
→ Ruff lint passed
→ 93 files already formatted
→ mypy: no issues in 93 source files
→ exit 0
```

```text
python -m pytest
→ 721 passed, 1 skipped

python -m pytest -m "not integration"
→ 702 passed, 20 deselected

python -m pytest -m integration
→ 19 passed, 1 skipped, 702 deselected

python -m pytest -m midi_integration
→ 9 passed, 713 deselected

python -m pytest -m baseline_integration
→ 1 skipped, 721 deselected
```

```text
python -m pytest --cov=saxo_ai --cov-report=term-missing --cov-report=xml
→ 721 passed, 1 skipped
→ 92.28% coverage
→ exit 0

python -m ruff check src tests scripts
→ passed

python -m ruff format --check src tests scripts
→ 93 files already formatted

python -m mypy
→ no issues in 93 source files
```

El único skip en Python 3.13 es la inferencia real fijada a Python 3.11.

## Matriz protegida funcional

Quality #183 (`29834537323`) pasó sobre el árbol funcional y documental previo al runner temporal:

```text
head: 7eed6cda87eeb83a8b00dcf541df0cd1fefb8203
Python 3.11 — success
Python 3.12 — success
Python 3.13 — success
```

Python 3.11 instaló FFmpeg y el baseline fijado, verificó procedencia PEP 610, checkpoint, checksum e inferencia CPU real, y ejecutó integración MIDI, cobertura, Ruff, formato y mypy. Python 3.12/3.13 instalaron el núcleo normal, ejecutaron FFmpeg, integración MIDI y el gate completo, omitiendo únicamente la inferencia real fijada a 3.11.

## Arquitectura y regresión

Los módulos SAX-033 no importan FastAPI, Mido, Torch, Hugging Face, librosa, NumPy, subprocess, tempfile ni herramientas de notación. No se agregó infraestructura.

El workflow protegido no fue modificado. SAX-021 baseline, SAX-031 MIDI y SAX-032 tempo no tuvieron cambios funcionales. Backend y Frontend no fueron modificados.

## Historias no implementadas

SAX-034 no comenzó. No existen compases, time signature, key signature, nombres de notas, accidentales, tuplets escritos, ligaduras, ties, beams, MusicXML, PDF, SVG, partitura, reproducción, persistencia, endpoint, job state, worker, cola, entrenamiento ni segundo baseline.
