# Dataset provenance and license registry — v1

## Objective

SAX-050 establishes a versioned, machine-readable dataset-governance contract so future experiments cannot use or redistribute data without an explicit record of provenance, official evidence, access mode, license terms and conservative use decisions.

The registry captures evidence and project decisions. It does not grant permission, replace official terms, constitute legal advice, guarantee legality or convert missing information into permission.

## Traceability

```text
SAX-050
→ R-004 data strategy
→ DATASET_REGISTRY_SCHEMA_VERSION 1.0
→ DatasetProvenanceRecord
→ DatasetLicense
→ DatasetUseRule
→ dataset-registry/registry-v1.json
→ tests/unit/test_dataset_provenance.py
→ tests/unit/test_dataset_registry_json.py
→ tests/integration/test_dataset_registry_catalog.py
```

No new RF identifier is introduced.

## Scope

Version `1.0` is dataset-level governance metadata only. It records stable identity, creators, publisher, release reference, canonical source, DOI, access mode, license summary, use decisions and official evidence.

SAX-051 remains responsible for file-level preparation such as individual recordings, manifests, checksums, raw/processed locations, annotation versions and reproducible acquisition procedures. SAX-050 contains none of those elements.

## Architecture

```text
domain
  immutable contracts and invariants

infrastructure
  strict UTF-8 JSON decoding with the Python standard library

documentation
  official sources, conservative decisions and limitations
```

No application case, mutable repository, database, HTTP endpoint or FastAPI composition is added because SAX-050 has no demonstrated runtime query requirement.

The domain module does not import `json`, `pathlib`, FastAPI, network clients, Zenodo SDKs, Hugging Face or PyTorch. Infrastructure performs offline JSON loading only.

## Schema version

```python
DATASET_REGISTRY_SCHEMA_VERSION = "1.0"
```

The top-level JSON form is:

```json
{
  "schema_version": "1.0",
  "datasets": []
}
```

The tracked registry requires the exact version, a non-empty dataset array, unique identifiers and deterministic sorting by `dataset_id`. Missing fields, unknown fields, duplicate JSON keys, future versions, nulls and incorrect types are rejected.

## Immutable contracts

All final domain contracts use frozen slotted dataclasses, immutable tuples and strict enums:

```text
DatasetAccessMode
DatasetLicenseKind
DatasetUse
DatasetUseDecision
DatasetEvidenceKind
DatasetEvidence
DatasetUseRule
DatasetLicense
DatasetProvenanceRecord
DatasetRegistry
```

Unvalidated dictionaries are confined to the infrastructure decoding boundary and never become the final domain contract.

## Enums

### DatasetAccessMode

```text
open
restricted
closed
project_generated
```

### DatasetLicenseKind

```text
spdx
custom
```

`spdx` requires an explicit SPDX identifier. `custom` uses a stable internal identifier without pretending that custom terms are an SPDX license. FiloSax uses `custom` and `filosax-custom-terms`.

### DatasetUse

```text
download
internal_noncommercial_research
commercial_use
redistribution
reproduction_material_distribution
publication_of_results
derived_asset_distribution
```

### DatasetUseDecision

```text
allowed
allowed_with_conditions
prohibited
requires_permission
not_stated
```

A use decision is never reduced to a Boolean. Conditions remain attached to conditional and permission-based decisions. `not_stated` remains explicit and carries no permission claim.

### DatasetEvidenceKind

```text
official_documentation
repository_record
paper
```

## DatasetEvidence

Each evidence value contains:

```text
kind
uri
reviewed_on
```

Evidence URIs must use HTTPS, reference a public host and contain no credentials, local paths, `file://`, path traversal or localhost. `reviewed_on` is a real ISO date in `YYYY-MM-DD` form.

The loader performs no requests. Evidence is reviewed manually and stored as public metadata only.

## DatasetLicense

Fields:

```text
kind
identifier
title
terms_uri
attribution_required
required_citation
terms_may_change
```

The terms URI must use safe HTTPS. The registry stores a structured conservative summary and a reference, never the full license text. `attribution_required=true` requires a non-empty citation. Boolean fields reject integers such as `0` and `1`.

`terms_may_change` records that official terms can change and should be reviewed again before future use.

## DatasetUseRule

Fields:

```text
use
decision
conditions
```

Every dataset contains exactly one rule for each `DatasetUse`, in enum order. Conditions are immutable tuples of non-empty strings. Conditional use and permission requirements preserve their conditions. `not_stated` has an empty condition tuple and must not imply permission.

## DatasetProvenanceRecord

Fields:

```text
dataset_id
title
creators
publisher
release_reference
canonical_uri
doi
access_mode
license
use_rules
evidence
```

Invariants include:

- safe stable lowercase `dataset_id`;
- non-empty title, publisher and release reference;
- non-empty unique creator tuple;
- safe canonical HTTPS URI;
- DOI stored as a DOI reference rather than a URL;
- supported access mode and license contract;
- every use category exactly once and in deterministic order;
- non-empty unique evidence.

No participant identity, performer list, email, token, cookie, credential or local cache path is recorded.

## DatasetRegistry

The registry is immutable, non-empty, exact-versioned and sorted. Dataset identifiers are unique. JSON arrays are converted to domain tuples only after structural validation.

The strict loader rejects:

- malformed JSON and duplicate object keys;
- missing or unknown fields at every level;
- unsupported enums or decisions;
- future schema versions;
- empty or duplicate datasets;
- unsorted datasets and use rules;
- arrays where objects are required and objects where arrays are required;
- nulls and integer substitutes for Boolean values.

## Example

```json
{
  "schema_version": "1.0",
  "datasets": [
    {
      "dataset_id": "example-dataset",
      "title": "Example Dataset",
      "creators": ["Researcher One"],
      "publisher": "Example Repository",
      "release_reference": "repository-record-123",
      "canonical_uri": "https://example.org/records/123",
      "doi": "10.1234/example.123",
      "access_mode": "restricted",
      "license": {
        "kind": "custom",
        "identifier": "example-custom-terms",
        "title": "Example restricted terms",
        "terms_uri": "https://example.org/terms",
        "attribution_required": true,
        "required_citation": "Example citation.",
        "terms_may_change": true
      },
      "use_rules": [],
      "evidence": []
    }
  ]
}
```

The abbreviated arrays above are explanatory only. A valid registry must include all seven use rules and at least one evidence entry.

## Initial catalog: FiloSax

The versioned catalog contains exactly one real dataset:

```text
dataset_id: filosax
title: Filosax
creators: Dave Foster; Simon Dixon
publisher: Zenodo
release_reference: zenodo-record-6335779
doi: 10.5281/zenodo.6335779
access_mode: restricted
license kind: custom
license identifier: filosax-custom-terms
reviewed_on: 2026-07-23
```

FiloSax is not represented as open, CC-BY, MIT, public domain, commercially usable or redistributable.

## Official sources

The record was reviewed manually on `2026-07-23` against:

```text
official documentation:
https://dave-foster.github.io/filosax/

repository record:
https://zenodo.org/records/6335779
https://doi.org/10.5281/zenodo.6335779

paper record:
https://zenodo.org/records/5625643
```

Blogs, mirrors, Kaggle, unofficial repositories, generated summaries and search snippets are not license evidence.

## FiloSax decisions

```text
download
  requires_permission

internal_noncommercial_research
  allowed_with_conditions

commercial_use
  prohibited

redistribution
  prohibited

reproduction_material_distribution
  prohibited

publication_of_results
  allowed_with_conditions

derived_asset_distribution
  not_stated
```

Recorded conditions preserve restricted access, non-commercial research, use by the authorized person and their group or organization, non-transferability, compliance with official terms, prohibition of sale/lease/publication/distribution to third parties without written administrator permission, prohibition of distributing material that enables reconstruction, and clear attribution in published results.

The required citation is:

```text
D. Foster and S. Dixon (2021), Filosax: A Dataset of Annotated Jazz Saxophone Recordings, 22nd International Society for Music Information Retrieval Conference.
```

No paper DOI is invented.

## `not_stated`

Distribution of derived datasets, extracted features, embeddings, trained checkpoints, adjusted weights and error examples is recorded as `not_stated`. SAX-050 makes no permission claim for those assets. A separate terms review is required before any such distribution.

## Security and privacy

The registry rejects credentialed, local, insecure and traversal URIs. It stores public governance metadata only. It contains no dataset payload, audio, annotations, participants, performer identities, personal identifiers, credentials, cache paths or machine paths.

Tests use synthetic JSON, fixed dates and fictitious HTTPS URIs. They make no network request and require no restricted access.

## Legal boundary

This registry records evidence and conservative project decisions. It is not legal advice and does not certify that an activity is lawful. Official terms remain authoritative and may change. Absence of a stated rule is never interpreted as permission.

## Limitations

SAX-050 does not download or prepare FiloSax. It does not implement file manifests, recording IDs, file checksums, backing-track reconstruction, raw/processed layouts, splits, data-leakage policy, metrics, evaluation, training, model cards, storage, APIs or authentication.

## Future extensions

SAX-051 may add a reproducible file-level preparation process after access and legal conditions are separately satisfied. Later schema versions may add dataset-level fields only through explicit version evolution and migration; version `1.0` rejects unknown future fields.
