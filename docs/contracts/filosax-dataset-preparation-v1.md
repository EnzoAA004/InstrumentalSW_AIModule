# Filosax reproducible dataset preparation — v1

## Objective

SAX-051 makes a locally, legally obtained Filosax copy reproducible across
machines: a deterministic manifest with a SHA-256 checksum per file, a
raw/processed directory separation rule, and a documented manual access
procedure. It never downloads, stores, or redistributes Filosax content.

## Traceability

```text
SAX-051
→ SAX-050 dataset-registry/registry-v1.json ("filosax" entry, access_mode=restricted)
→ DATASET_MANIFEST_SCHEMA_VERSION 1.0
→ DatasetManifest / DatasetManifestEntry
→ validate_distinct_dataset_roots
→ scripts/prepare_filosax_dataset.py
→ tests/unit/test_dataset_manifest.py
→ tests/unit/test_dataset_layout.py
→ tests/integration/test_dataset_manifest_fs.py
→ tests/integration/test_prepare_filosax_dataset_cli.py
```

## Manual access procedure (operator responsibility, not automated)

Filosax's `download` use rule in the dataset registry is `requires_permission`.
This project does not and will not automate acquisition of restricted files.
The operator must, on their own account:

1. Read the official terms at <https://dave-foster.github.io/filosax/>.
2. Request/accept access to the restricted Zenodo record
   (`https://zenodo.org/records/6335779`), or start with the smaller
   "Filosax Lite" (2 tracks) for local testing of this tooling.
3. Optionally purchase the backing tracks separately from jazzbooks.com and
   compile them into a `/Backing` folder using the project's own scripts, per
   the official instructions.
4. Place the resulting files under a local raw directory, e.g.
   `data/raw/filosax/` (already covered by `.gitignore`'s `data/` rule —
   nothing under it is ever committed).

## Expected raw content (per official documentation)

Each of the (up to 48) pieces distributes, per the official site:

- 7 audio stems: `Bass_Drums`, `Piano_Drums`, and 5 individual saxophonist
  ("Participant 1"–"Participant 5") mono recordings.
- Annotation files: `.jams` (beat/chord/section) and `.json` (per-saxophone
  note-level pitch/timing/dynamics/vibrato).
- MIDI transcriptions, plus PDF and MusicXML scores.

This project does not hardcode exact filenames because the operator's local
copy composition (full vs. Lite, with or without compiled `/Backing`) varies
legitimately. `prepare_filosax_dataset.py manifest` records whatever files are
actually present; it does not assert a fixed file count.

## Raw / processed separation

`saxo_ai.domain.dataset_layout.validate_distinct_dataset_roots` rejects a raw
root and a processed root that are equal or nested inside one another. Future
preparation steps (SAX-052+) that derive processed audio or splits from the
raw copy must call this guard before writing anything, so derived output can
never be mistaken for — or silently overwrite — the original source.

## Manifest schema version

```python
DATASET_MANIFEST_SCHEMA_VERSION = "1.0"
```

```json
{
  "schema_version": "1.0",
  "dataset_id": "filosax",
  "files": [
    {"relative_path": "P1/take1.wav", "size_bytes": 123456, "sha256": "…64 hex…"}
  ]
}
```

`files` must be sorted by `relative_path`, contain unique paths, and every
path must be a safe POSIX-relative path (no leading `/`, no `..`, no drive
letters, no backslashes).

## CLI

```bash
python scripts/prepare_filosax_dataset.py manifest data/raw/filosax data/raw/filosax.manifest.json
python scripts/prepare_filosax_dataset.py verify data/raw/filosax data/raw/filosax.manifest.json
```

Both commands first confirm `"filosax"` is registered in
`dataset-registry/registry-v1.json` (governance precedes preparation) and then
hash the raw directory. `verify` re-hashes the directory and reports missing,
unexpected, and checksum-mismatched files relative to a previously captured
manifest, exiting non-zero when the copy is not bit-for-bit reproducible.

## Architecture

```text
domain
  DatasetManifest / DatasetManifestEntry immutable contracts, comparison,
  and raw/processed separation — no I/O.

infrastructure
  filesystem walk + SHA-256 hashing, strict UTF-8 JSON encode/decode.

scripts
  thin CLI wiring, mirroring scripts/install_baseline.py.
```

## Limitations

- No dataset files are bundled, downloaded, or distributed by this project.
- The exact Filosax file count/layout is not asserted; only structural safety
  (safe relative paths, uniqueness, sorted order) and checksum reproducibility
  are enforced.
- Splitting into train/validation/test (leakage-safe) is SAX-052, not this
  story.
