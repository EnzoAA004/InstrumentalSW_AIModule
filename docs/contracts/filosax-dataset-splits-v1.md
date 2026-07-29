# Filosax leakage-safe dataset splits — v1

## Objective

SAX-052 turns a SAX-051 manifest into a deterministic train/validation/test
split plan where every file that shares a group never spans more than one
split, so a piece the model saw in training can never leak into validation
or test through a different take, stem, or annotation file.

## Traceability

```text
SAX-052
→ SAX-051 dataset manifest (dataset_id="filosax")
→ DATASET_SPLIT_PLAN_SCHEMA_VERSION 1.0
→ DatasetSplitPlan / DatasetSplitAssignment / DatasetSplitProportions
→ AssignDatasetSplits (application use case)
→ scripts/split_filosax_dataset.py
→ tests/unit/test_dataset_splits.py
→ tests/unit/test_dataset_split_planning.py
→ tests/integration/test_dataset_split_plan_json.py
→ tests/integration/test_split_filosax_dataset_cli.py
```

## Grouping strategy and its assumption

Groups are the first path segment of each file's manifest-relative path
(`saxo_ai.application.dataset_split_planning.top_level_directory_group_key`).
This assumes the raw copy is organized as one directory per piece/session,
e.g. `data/raw/filosax/<piece-id>/...`. If an operator's local copy is
organized differently (e.g. one directory per stem type instead of per
piece), it must be reorganized before splitting — grouping by directory only
prevents leakage if the directory boundary actually matches the musical
boundary you want to keep out of both sets.

`DatasetSplitPlan` itself enforces the leakage invariant independently of the
grouping choice: construction raises if any `group_key` maps to more than one
`DatasetSplitName`. A caller cannot silently produce a leaking plan.

## Known limitation: performer generalization

Filosax's per-piece stems are recorded by the same small set of
saxophonists across (up to) all 48 pieces. Splitting by piece alone measures
generalization to unseen material played by *known* performers, not to
unseen performers — with only a handful of saxophonists in the whole
dataset, held-out-performer evaluation is not practical here. This is
recorded as a limitation for SAX-053/SAX-054 metric interpretation, not
solved by this story.

## Deterministic assignment

`AssignDatasetSplits` hashes `f"{seed}:{group_key}"` with SHA-256 and buckets
the first 8 bytes into `[0, 1)` against cumulative `train`/`validation`/`test`
thresholds. This is:

- **Deterministic**: the same `(seed, group_key)` always yields the same
  split, so regenerating a plan from an unchanged manifest and seed is a
  byte-identical no-op.
- **Group-count-approximate, not file-count-exact**: because whole groups
  (which can contain a different number of files) are assigned atomically,
  realized file-level proportions approach — but do not exactly equal — the
  configured proportions. With enough groups this converges close to target.

## Schema version

```python
DATASET_SPLIT_PLAN_SCHEMA_VERSION = "1.0"
```

```json
{
  "schema_version": "1.0",
  "dataset_id": "filosax",
  "proportions": {"train": 0.7, "validation": 0.15, "test": 0.15},
  "assignments": [
    {"relative_path": "piece-001/take1.wav", "group_key": "piece-001", "split": "train"}
  ]
}
```

## CLI

```bash
python scripts/split_filosax_dataset.py data/raw/filosax.manifest.json data/raw/filosax.split-plan.json
```

Optional `--train`, `--validation`, `--test` (must sum to 1.0) and `--seed`
override the defaults (`0.7`/`0.15`/`0.15`, fixed project seed). Changing the
seed intentionally reshuffles the group-to-split assignment.

## Architecture

```text
domain
  DatasetSplitPlan / DatasetSplitAssignment / DatasetSplitProportions —
  immutable, enforces the no-leakage invariant, no I/O.

application
  AssignDatasetSplits — deterministic hash-bucket assignment over a
  DatasetManifest and a pluggable group-key function.

infrastructure
  Strict UTF-8 JSON encode/decode, mirroring the SAX-051/SAX-050 pattern.

scripts
  Thin CLI wiring, mirroring scripts/prepare_filosax_dataset.py.
```
