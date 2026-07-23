from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from saxo_ai.domain.dataset_provenance import (
    DATASET_REGISTRY_SCHEMA_VERSION,
    DatasetAccessMode,
    DatasetEvidence,
    DatasetEvidenceKind,
    DatasetLicense,
    DatasetLicenseKind,
    DatasetProvenanceRecord,
    DatasetRegistry,
    DatasetUse,
    DatasetUseDecision,
    DatasetUseRule,
    InvalidDatasetProvenanceError,
)

REVIEWED_ON = "2026-07-23"
CITATION = (
    "D. Foster and S. Dixon (2021), Filosax: A Dataset of Annotated Jazz "
    "Saxophone Recordings, 22nd International Society for Music Information "
    "Retrieval Conference."
)


def valid_evidence() -> tuple[DatasetEvidence, ...]:
    return (
        DatasetEvidence(
            kind=DatasetEvidenceKind.OFFICIAL_DOCUMENTATION,
            uri="https://example.org/dataset/terms",
            reviewed_on=REVIEWED_ON,
        ),
    )


def valid_license() -> DatasetLicense:
    return DatasetLicense(
        kind=DatasetLicenseKind.CUSTOM,
        identifier="example-custom-terms",
        title="Example restricted dataset terms",
        terms_uri="https://example.org/dataset/terms",
        attribution_required=True,
        required_citation=CITATION,
        terms_may_change=True,
    )


def valid_use_rules() -> tuple[DatasetUseRule, ...]:
    decisions = {
        DatasetUse.DOWNLOAD: DatasetUseDecision.REQUIRES_PERMISSION,
        DatasetUse.INTERNAL_NONCOMMERCIAL_RESEARCH: (
            DatasetUseDecision.ALLOWED_WITH_CONDITIONS
        ),
        DatasetUse.COMMERCIAL_USE: DatasetUseDecision.PROHIBITED,
        DatasetUse.REDISTRIBUTION: DatasetUseDecision.PROHIBITED,
        DatasetUse.REPRODUCTION_MATERIAL_DISTRIBUTION: (
            DatasetUseDecision.PROHIBITED
        ),
        DatasetUse.PUBLICATION_OF_RESULTS: (
            DatasetUseDecision.ALLOWED_WITH_CONDITIONS
        ),
        DatasetUse.DERIVED_ASSET_DISTRIBUTION: DatasetUseDecision.NOT_STATED,
    }
    return tuple(
        DatasetUseRule(
            use=dataset_use,
            decision=decisions[dataset_use],
            conditions=(
                ()
                if decisions[dataset_use] is DatasetUseDecision.NOT_STATED
                else ("Follow the official terms.",)
            ),
        )
        for dataset_use in DatasetUse
    )


def valid_record() -> DatasetProvenanceRecord:
    return DatasetProvenanceRecord(
        dataset_id="example-dataset",
        title="Example Dataset",
        creators=("Researcher One", "Researcher Two"),
        publisher="Example Repository",
        release_reference="repository-record-123",
        canonical_uri="https://example.org/records/123",
        doi="10.1234/example.123",
        access_mode=DatasetAccessMode.RESTRICTED,
        license=valid_license(),
        use_rules=valid_use_rules(),
        evidence=valid_evidence(),
    )


def test_enums_expose_only_the_versioned_contract_values() -> None:
    assert DATASET_REGISTRY_SCHEMA_VERSION == "1.0"
    assert tuple(value.value for value in DatasetAccessMode) == (
        "open",
        "restricted",
        "closed",
        "project_generated",
    )
    assert tuple(value.value for value in DatasetLicenseKind) == ("spdx", "custom")
    assert tuple(value.value for value in DatasetUse) == (
        "download",
        "internal_noncommercial_research",
        "commercial_use",
        "redistribution",
        "reproduction_material_distribution",
        "publication_of_results",
        "derived_asset_distribution",
    )
    assert tuple(value.value for value in DatasetUseDecision) == (
        "allowed",
        "allowed_with_conditions",
        "prohibited",
        "requires_permission",
        "not_stated",
    )
    assert tuple(value.value for value in DatasetEvidenceKind) == (
        "official_documentation",
        "repository_record",
        "paper",
    )
    with pytest.raises(ValueError):
        DatasetUseDecision("unknown")


@pytest.mark.parametrize(
    "dataset_id",
    ["", "FiloSax", "filo sax", "filosax/path", "filosax\\path", "../filosax"],
)
def test_dataset_id_rejects_unsafe_or_unstable_values(dataset_id: str) -> None:
    with pytest.raises(InvalidDatasetProvenanceError):
        replace(valid_record(), dataset_id=dataset_id)


def test_valid_provenance_is_frozen_slotted_and_tuple_based() -> None:
    record = valid_record()
    registry = DatasetRegistry(DATASET_REGISTRY_SCHEMA_VERSION, (record,))

    assert record.dataset_id == "example-dataset"
    assert isinstance(record.creators, tuple)
    assert isinstance(record.use_rules, tuple)
    assert isinstance(record.evidence, tuple)
    assert not hasattr(record, "__dict__")
    assert not hasattr(registry, "__dict__")
    with pytest.raises(FrozenInstanceError):
        record.title = "Changed"  # type: ignore[misc]


def test_provenance_rejects_missing_or_duplicate_identity_fields() -> None:
    with pytest.raises(InvalidDatasetProvenanceError):
        replace(valid_record(), creators=())
    with pytest.raises(InvalidDatasetProvenanceError):
        replace(valid_record(), creators=("Researcher One", "Researcher One"))
    with pytest.raises(InvalidDatasetProvenanceError):
        replace(valid_record(), creators=("Researcher One", ""))
    with pytest.raises(InvalidDatasetProvenanceError):
        replace(valid_record(), publisher="")
    with pytest.raises(InvalidDatasetProvenanceError):
        replace(valid_record(), release_reference="")
    with pytest.raises(InvalidDatasetProvenanceError):
        replace(valid_record(), title="")
    with pytest.raises(InvalidDatasetProvenanceError):
        replace(valid_record(), evidence=())


@pytest.mark.parametrize(
    "uri",
    [
        "http://example.org/terms",
        "file:///tmp/terms",
        "https://user:password@example.org/terms",
        "https://localhost/terms",
        "C:\\terms",
        "/tmp/terms",
        "../terms",
        "https://example.org/../private",
    ],
)
def test_evidence_rejects_insecure_local_or_credentialed_uris(uri: str) -> None:
    with pytest.raises(InvalidDatasetProvenanceError):
        DatasetEvidence(
            kind=DatasetEvidenceKind.OFFICIAL_DOCUMENTATION,
            uri=uri,
            reviewed_on=REVIEWED_ON,
        )


@pytest.mark.parametrize(
    "reviewed_on",
    ["", "2026/07/23", "23-07-2026", "2026-02-30"],
)
def test_evidence_requires_a_real_iso_date(reviewed_on: str) -> None:
    with pytest.raises(InvalidDatasetProvenanceError):
        DatasetEvidence(
            kind=DatasetEvidenceKind.PAPER,
            uri="https://example.org/paper",
            reviewed_on=reviewed_on,
        )


@pytest.mark.parametrize(
    "canonical_uri",
    [
        "http://example.org/123",
        "file:///tmp/123",
        "https://localhost/123",
        "/tmp/123",
    ],
)
def test_provenance_requires_a_secure_canonical_uri(canonical_uri: str) -> None:
    with pytest.raises(InvalidDatasetProvenanceError):
        replace(valid_record(), canonical_uri=canonical_uri)


@pytest.mark.parametrize(
    "doi",
    [
        "",
        "https://doi.org/10.1234/example.123",
        "doi:10.1234/example",
        "example.123",
    ],
)
def test_provenance_rejects_invalid_doi_references(doi: str) -> None:
    with pytest.raises(InvalidDatasetProvenanceError):
        replace(valid_record(), doi=doi)


def test_custom_and_explicit_spdx_licenses_are_distinct() -> None:
    custom = valid_license()
    spdx = replace(
        custom,
        kind=DatasetLicenseKind.SPDX,
        identifier="CC-BY-4.0",
        title="Creative Commons Attribution 4.0 International",
    )

    assert custom.kind is DatasetLicenseKind.CUSTOM
    assert spdx.kind is DatasetLicenseKind.SPDX
    with pytest.raises(InvalidDatasetProvenanceError):
        replace(spdx, identifier="")


@pytest.mark.parametrize(
    "terms_uri",
    [
        "http://example.org/terms",
        "file:///tmp/terms",
        "https://localhost/terms",
        "../terms",
    ],
)
def test_license_requires_an_https_terms_uri(terms_uri: str) -> None:
    with pytest.raises(InvalidDatasetProvenanceError):
        replace(valid_license(), terms_uri=terms_uri)


def test_attribution_and_terms_change_flags_are_strict() -> None:
    with pytest.raises(InvalidDatasetProvenanceError):
        replace(valid_license(), required_citation="")
    with pytest.raises(InvalidDatasetProvenanceError):
        replace(valid_license(), attribution_required=1)  # type: ignore[arg-type]
    with pytest.raises(InvalidDatasetProvenanceError):
        replace(valid_license(), terms_may_change=0)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_conditions", [[], ("",), ("valid", "   ")])
def test_use_rule_requires_a_tuple_of_non_empty_conditions(
    bad_conditions: object,
) -> None:
    with pytest.raises(InvalidDatasetProvenanceError):
        DatasetUseRule(
            use=DatasetUse.DOWNLOAD,
            decision=DatasetUseDecision.REQUIRES_PERMISSION,
            conditions=bad_conditions,  # type: ignore[arg-type]
        )


def test_not_stated_is_preserved_without_permission_claims() -> None:
    rule = DatasetUseRule(
        use=DatasetUse.DERIVED_ASSET_DISTRIBUTION,
        decision=DatasetUseDecision.NOT_STATED,
        conditions=(),
    )
    assert rule.decision is DatasetUseDecision.NOT_STATED
    with pytest.raises(InvalidDatasetProvenanceError):
        replace(rule, conditions=("Distribution is allowed.",))


def test_record_requires_every_use_once_in_deterministic_order() -> None:
    rules = valid_use_rules()
    with pytest.raises(InvalidDatasetProvenanceError):
        replace(valid_record(), use_rules=rules[:-1])
    with pytest.raises(InvalidDatasetProvenanceError):
        replace(valid_record(), use_rules=(*rules[:-1], rules[0]))
    with pytest.raises(InvalidDatasetProvenanceError):
        replace(valid_record(), use_rules=(rules[1], rules[0], *rules[2:]))


def test_registry_requires_exact_version_unique_sorted_non_empty_datasets() -> None:
    first = valid_record()
    second = replace(first, dataset_id="second-dataset", title="Second Dataset")

    assert DatasetRegistry("1.0", (first, second)).datasets == (first, second)
    with pytest.raises(InvalidDatasetProvenanceError):
        DatasetRegistry("2.0", (first,))
    with pytest.raises(InvalidDatasetProvenanceError):
        DatasetRegistry("1.0", ())
    with pytest.raises(InvalidDatasetProvenanceError):
        DatasetRegistry("1.0", (first, first))
    with pytest.raises(InvalidDatasetProvenanceError):
        DatasetRegistry("1.0", (second, first))
