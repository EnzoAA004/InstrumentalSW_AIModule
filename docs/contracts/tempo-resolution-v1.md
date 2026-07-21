# Tempo resolution contract v1

## Alcance

SAX-032 resuelve un tempo para un `WrittenPitchTranscriptionResult`. Puede estimar desde onsets, configurar BPM manual, crear overrides inmutables y regenerar MIDI con SAX-031.

No analiza audio, no ejecuta transcripción, no cuantiza notas y no conecta FastAPI, jobs, almacenamiento, Backend o Frontend.

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

No se agrega un identificador RF nuevo.

## Versiones y defaults

```text
policy_version          1.0
estimator_name          median_onset_interval
estimator_version       1.0
confidence_method       octave_equivalent_ioi_consensus_ratio
minimum_bpm             40.0
maximum_bpm            240.0
minimum_interval_count    2
consensus_tolerance       0.08
```

## Validación BPM común

`normalize_positive_bpm` acepta únicamente `int` o `float` finitos y positivos, rechaza booleanos y normaliza a `float`.

`TempoEstimationSettings` agrega el rango configurado. `MidiExportSettings` conserva la validación SAX-031 del valor de tempo MIDI de tres bytes. La refactorización no cambia el rango público ya aceptado por SAX-031.

## Settings

`TempoEstimationSettings` es frozen y slotted.

Invariantes:

- BPM mínimo y máximo finitos y positivos;
- mínimo menor que máximo;
- cantidad mínima de intervalos entera positiva y no booleana;
- tolerancia finita dentro de `0.0..1.0`;
- versión exactamente `1.0`.

No usa variables de entorno.

## Puerto

```python
@runtime_checkable
class TempoEstimator(Protocol):
    def estimate(
        self,
        original: WrittenPitchTranscriptionResult,
        settings: TempoEstimationSettings,
    ) -> AutomaticTempoEstimate:
        ...
```

El puerto no importa FastAPI ni Mido, no recibe paths, archivos o audio y no modifica eventos.

## Estimador de intervalos entre onsets

`OnsetIntervalTempoEstimator` usa solo biblioteca estándar y lee exclusivamente:

```python
event.source.event.onset_seconds
```

Proceso:

1. reúne todos los onsets;
2. elimina únicamente duplicados exactamente iguales para la estimación;
3. ordena los onsets únicos;
4. calcula diferencias consecutivas positivas;
5. calcula `raw_bpm = 60.0 / interval_seconds`;
6. usa la mediana de candidatos;
7. si la mediana está fuera de rango, aplica potencias de dos hasta encontrar una equivalencia válida;
8. nunca recorta al mínimo o máximo.

Los eventos originales no se eliminan, reordenan ni reconstruyen.

## Equivalencia por octavas y consenso

Para cada candidato se consideran sus equivalencias por potencias de dos dentro del rango. Se selecciona la más cercana al BPM estimado; un empate elige el valor menor.

Un intervalo es inlier cuando:

```text
abs(candidate_equivalent - estimated_bpm) / estimated_bpm
<= consensus_tolerance
```

La confianza es exactamente:

```text
inlier_interval_count / interval_count
```

La confianza expresa consistencia interna de IOIs equivalentes por octavas. No es probabilidad calibrada ni garantía musical.

**Confidence `0.8` no significa 80 % de exactitud del tempo.**

## AutomaticTempoEstimate

Contrato frozen y slotted con:

```text
tempo_bpm
confidence
estimator_name
estimator_version
confidence_method
unique_onset_count
interval_count
inlier_interval_count
```

Invariantes:

- BPM positivo y finito;
- confidence dentro de `0.0..1.0`;
- strings no vacíos;
- contadores enteros no negativos;
- `interval_count == unique_onset_count - 1`;
- inliers no mayores que intervalos;
- confidence igual al cociente documentado.

## Material insuficiente

Con el default se requieren al menos tres onsets únicos. Lote vacío, una nota o dos onsets únicos producen `TempoEstimationUnavailableError`.

El error conserva:

```text
unique_onset_count
interval_count
minimum_interval_count
```

El modo manual sigue disponible con material insuficiente.

## Selección y revisiones

```python
class TempoSelectionSource(StrEnum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"
```

`TempoResolution` conserva original, estimate automático opcional, BPM manual opcional, BPM efectivo, source, revision y policy version.

Fuente automática:

```text
automatic_estimate presente
manual_tempo_bpm ausente
effective == automatic estimate
revision == 1
```

Fuente manual:

```text
manual_tempo_bpm presente
effective == manual
revision >= 1
```

Una selección manual directa puede no tener estimate automático. Un override conserva `original` y `automatic_estimate` por identidad.

## Casos de uso

`EstimateTranscriptionTempo` valida, llama al puerto una vez, conserva el estimate completo y crea revisión automática 1. No exporta MIDI.

`ConfigureManualTempo` crea revisión manual 1 incluso con lote vacío o material insuficiente.

`OverrideEstimatedTempo` crea un objeto nuevo, conserva referencias, selecciona BPM manual e incrementa revision. Cada override explícito crea revisión aunque el BPM coincida con el anterior.

## Regeneración MIDI

`ExportTempoResolvedMidi` reutiliza `ExportWrittenPitchToMidi` y `MidiExportSettings`.

```python
TempoResolvedMidiResult(
    tempo=tempo_resolution_used,
    midi=midi_export_result,
)
```

Invariantes:

```python
result.midi.original is result.tempo.original
result.midi.report.settings.tempo_bpm == result.tempo.effective_tempo_bpm
```

Un cambio de BPM regenera el metaevento de tempo y los ticks. El resultado previo permanece intacto.

SAX-031 conserva MIDI type 1, 480 ticks por beat, dos tracks, canal 0, concert pitch, velocity policy, ordering, bytes y SHA deterministas.

## Contrato futuro con SAX-033

SAX-033 no está implementada. Un futuro resultado cuantizado deberá conservar la misma referencia o revisión de `TempoResolution` usada para derivarlo, evitando reutilizar derivados de una revisión anterior.

No se agregan notas cuantizadas, rejillas, figuras, silencios ni compás.

## Errores

```text
InvalidTempoSettingsError
InvalidTempoEstimateError
TempoEstimationUnavailableError
TempoEstimatorError
InvalidTempoResolutionError
```

Los fallos inesperados del adaptador se envuelven sin incorporar eventos, modelo, checkpoint, paths o audio al mensaje estable.

## Complejidad

- estimación: `O(n log n)` tiempo y `O(n)` memoria;
- configuración manual: `O(1)`;
- override: `O(1)`;
- regeneración MIDI: `O(n log n)` por el planner existente y `O(n)` memoria.

## Limitaciones

El baseline puede escoger una equivalencia de octava distinta del beat musical pretendido. Rubato, tempo cambiante, material escaso, síncopas y subdivisiones mixtas pueden reducir o desviar el consenso.

No existe análisis espectral, beat tracking de audio, time stretching, métrica ni cuantización en SAX-032.
