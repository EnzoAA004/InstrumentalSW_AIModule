# Rhythm quantization contract v1

## Alcance

SAX-033 convierte los tiempos continuos de `TempoResolution.original.events` en una línea temporal monofónica cuantizada. La salida conserva la revisión exacta de tempo, cada `WrittenPitchNoteEvent` por referencia, los tiempos originales y la procedencia completa de SAX-021, SAX-022, SAX-023 y SAX-030.

No crea compases, indicación de compás, armadura, nombres de notas, figuras gráficas, puntillos, ligaduras, tuplets escritos, MusicXML, partitura ni renderizado. Tampoco conecta FastAPI, jobs, persistencia, Backend o Frontend.

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

No se agrega un identificador RF nuevo.

## Política y defaults

```text
policy_version          1.0
subdivisions_per_beat     4
rounding_mode            nearest_half_up
overlap_policy           truncate_earlier_then_shift_same_step
rest_policy              explicit_positive_grid_gaps
beat                     negra
```

La rejilla predeterminada tiene cuatro pasos uniformes por beat y representa semicorcheas matemáticas. También se permiten, entre otros, `1`, `2`, `3`, `4`, `6` y `8`. Los valores ternarios solo expresan una rejilla uniforme; SAX-033 no produce metadata de tuplet.

`RhythmQuantizationSettings` es frozen y slotted. `subdivisions_per_beat` debe ser un `int` real y positivo; rechaza booleanos, floats, strings y `None`. La versión debe ser exactamente `"1.0"`. No existe variable de entorno.

## Conversión segundos ↔ pasos

Para un BPM efectivo y `S` subdivisiones:

```text
beat_position = seconds × effective_tempo_bpm / 60
grid_position = beat_position × S
seconds_per_step = 60 / effective_tempo_bpm / S
quantized_seconds = grid_step × seconds_per_step
```

Las fórmulas están centralizadas en helpers de aplicación. No se agrega NumPy.

## Redondeo

La posición de rejilla se convierte con `Decimal(str(value))` y `ROUND_HALF_UP`. El empate avanza:

```text
0.49 → 0
0.50 → 1
1.49 → 1
1.50 → 2
```

El contrato no usa el redondeo bancario de `round()` para esta frontera.

## Candidatos y duración mínima

Onset y offset se cuantizan por separado desde:

```python
source.source.event.onset_seconds
source.source.event.offset_seconds
```

Si ambos bordes quedan en el mismo paso, o si el offset no supera al onset candidato, el offset se establece en `onset + 1`. La corrección incrementa `minimum_duration_adjustment_count`. Los segundos originales permanecen intactos.

## Orden

La colección original no se ordena ni se modifica. El caso de uso trabaja sobre referencias indexadas y ordena una copia por:

```text
original onset_seconds
original offset_seconds
pitch_concert_midi
source_index
```

Cada nota cuantizada conserva `source_index`, que apunta a la posición original exacta.

## Política monofónica de solapamientos

### Sin solapamiento

Cuando el onset actual es igual o posterior al offset anterior, ambas notas se conservan sin ajuste.

### Ataque posterior dentro de la nota anterior

Cuando:

```text
previous_onset < current_onset < previous_offset
```

el nuevo ataque se conserva y termina la nota anterior:

```text
previous_offset = current_onset
```

### Colisión en el mismo paso

Cuando el onset actual no supera al onset anterior, truncar la nota anterior produciría duración cero. El evento actual se desplaza al offset anterior y mantiene al menos un paso:

```text
current_onset = previous_offset
current_offset = max(current_offset, current_onset + 1)
```

No se elimina, fusiona o prioriza ninguna nota por pitch, velocity o confidence. `overlap_adjusted_event_count` cuenta eventos cuya frontera fue modificada por esta política.

## Notas cuantizadas

`QuantizedNoteEvent` es frozen y slotted y contiene:

```text
source
source_index
quantized_onset_step
quantized_offset_step
onset_delta_seconds
offset_delta_seconds
```

Invariantes:

- `source` es `WrittenPitchNoteEvent`;
- índice entero no negativo y no booleano;
- pasos enteros no negativos y no booleanos;
- offset estrictamente mayor que onset;
- deltas finitos.

El tiempo original continúa disponible a través de la referencia `source`. `duration_steps` se calcula y no se almacena de forma duplicada.

## Deltas de timing

Los deltas finales se calculan después de resolver duración mínima y solapamientos:

```text
onset_delta_seconds = quantized_onset_seconds - original_onset_seconds
offset_delta_seconds = quantized_offset_seconds - original_offset_seconds
```

Conservan signo y no se redondean. Un delta positivo representa una frontera notada más tarde y uno negativo una frontera más temprana.

## Silencios explícitos

`QuantizedRest` contiene un intervalo positivo `[onset_step, offset_step)` sin pitch, velocity o confidence.

Se genera:

- silencio inicial `[0, first_onset)` cuando la primera nota comienza después de cero;
- silencio interno para cada gap positivo entre notas;
- ningún silencio para notas adyacentes;
- ningún silencio de duración cero cuando un gap real colapsa en la rejilla;
- ningún silencio final, porque SAX-033 no conoce una duración total independiente.

Un lote vacío produce timeline vacío y no inventa duración.

## Timeline

`QuantizedRhythmResult.timeline` contiene notas y silencios en orden musical. Cuando no está vacío:

- comienza en el paso cero;
- todos los elementos tienen duración positiva;
- cada frontera final coincide con la frontera inicial siguiente;
- no hay solapamientos ni huecos no representados;
- no hay silencios consecutivos;
- no termina con silencio;
- cada evento original aparece exactamente una vez;
- cada nota conserva la referencia exacta indicada por `source_index`.

La validación de estas invariantes está centralizada en `QuantizedRhythmResult`.

## Reporte

`RhythmQuantizationReport` conserva los settings exactos y registra:

```text
input_event_count
quantized_note_count
rest_count
minimum_duration_adjustment_count
overlap_adjusted_event_count
total_absolute_onset_delta_seconds
total_absolute_offset_delta_seconds
maximum_absolute_boundary_delta_seconds
```

Invariantes:

```text
input_event_count = quantized_note_count
rest_count = cantidad de QuantizedRest en timeline
```

Todos los contadores son enteros no negativos y no booleanos. Las métricas son finitas y no negativas y se recalculan desde los deltas de las notas. Para lote vacío valen `0.0`.

Propiedades derivadas:

```text
total_absolute_timing_delta_seconds
mean_absolute_boundary_delta_seconds
```

## Revisión de tempo

El resultado almacena la misma instancia de `TempoResolution` utilizada:

```python
result.tempo is tempo_resolution_used
```

Por lo tanto permanecen accesibles BPM efectivo, source automático/manual, estimate automático y revision. Un override de SAX-032 seguido de otra cuantización produce un resultado nuevo asociado a la nueva revisión; el resultado anterior no se modifica ni se reutiliza silenciosamente.

## Preservación

SAX-033 no modifica ni copia como strings nuevas:

- `NoteEvent` y sus tiempos originales;
- pitch de concierto y pitch escrito;
- velocity y confidence;
- `is_low_confidence`;
- modelo, revisiones y checkpoint;
- settings y reportes previos;
- estimate automático, BPM manual o revision de tempo.

## Errores

```text
InvalidRhythmQuantizationSettingsError
InvalidQuantizedNoteError
InvalidQuantizedRestError
InvalidRhythmQuantizationReportError
InvalidQuantizedRhythmResultError
RhythmQuantizationError
```

Los errores de contrato se conservan. Un fallo inesperado del caso de uso se traduce a un mensaje estable que no incorpora lote, modelo, checkpoint, audio, rutas o stack trace.

## Complejidad

```text
ordenamiento: O(n log n)
resolución:   O(n)
silencios:    O(n)
memoria:      O(n)
```

No existe puerto ni adaptador externo para esta historia.

## Limitaciones

La rejilla es uniforme y parte del origen cero. La política monofónica es un baseline determinista y revisable. No interpreta swing, rubato, cambios de tempo, métrica, compases o intención de fraseo. Subdivisiones `3` o `6` no generan notación de tuplets. SAX-034 y MusicXML permanecen sin implementar.
