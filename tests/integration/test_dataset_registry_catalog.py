from __future__ import annotations

from pathlib import Path

import pytest

from saxo_ai.domain.dataset_provenance import (
    DATASET_REGISTRY_SCHEMA_VERSION,
    DatasetAccessMode,
    DatasetEvidenceKind,
    DatasetLicenseKind,
    DatasetUse,
    DatasetUseDecision,
)
from saxo_ai.infrastructure.dataset_registry_json import load_dataset_registry

pytestmark = pytest.mark.integration

REGISTRY_PATH = Path(__file__).resolve().parents[2] / "dataset-registry" / "registry-v1.json"


def test_tracked_registry_contains_only_restricted_filosax_governance_metadata() -> None:
    registry = load_dataset_registry(REGISTRY_PATH)

    assert registry.schema_version == DATASET_REGISTRY_SCHEMA_VERSION == "1.0"
    assert len(registry.datasets) == 1
    filosax = registry.datasets[0]
    assert filosax.dataset_id == "filosax"
    assert filosax.title == "Filosax"
    assert filosax.creators == ("Dave Foster", "Simon Dixon")
    assert filosax.publisher == "Zenodo"
    assert filosax.release_reference == "zenodo-record-6335779"
    assert filosax.canonical_uri == "https://zenodo.org/records/6335779"
    assert filosax.doi == "10.5281/zenodo.6335779"
    assert filosax.access_mode is DatasetAccessMode.RESTRICTED
    assert filosax.license.kind is DatasetLicenseKind.CUSTOM
    assert filosax.license.identifier == "filosax-custom-terms"
    assert filosax.license.attribution_required is True
    assert filosax.license.required_citation
    assert filosax.license.terms_may_change is True

    decisions = {rule.use: rule.decision for rule in filosax.use_rules}
    assert decisions == {
        DatasetUse.DOWNLOAD: DatasetUseDecision.REQUIRES_PERMISSION,
        DatasetUse.INTERNAL_NONCOMMERCIAL_RESEARCH: DatasetUseDecision.ALLOWED_WITH_CONDITIONS,
        DatasetUse.COMMERCIAL_USE: DatasetUseDecision.PROHIBITED,
        DatasetUse.REDISTRIBUTION: DatasetUseDecision.PROHIBITED,
        DatasetUse.REPRODUCTION_MATERIAL_DISTRIBUTION: DatasetUseDecision.PROHIBITED,
        DatasetUse.PUBLICATION_OF_RESULTS: DatasetUseDecision.ALLOWED_WITH_CONDITIONS,
        DatasetUse.DERIVED_ASSET_DISTRIBUTION: DatasetUseDecision.NOT_STATED,
    }
    derived = next(
        rule for rule in filosax.use_rules if rule.use is DatasetUse.DERIVED_ASSET_DISTRIBUTION
    )
    assert derived.conditions == ()

    evidence_kinds = {evidence.kind for evidence in filosax.evidence}
    assert evidence_kinds == {
        DatasetEvidenceKind.OFFICIAL_DOCUMENTATION,
        DatasetEvidenceKind.REPOSITORY_RECORD,
        DatasetEvidenceKind.PAPER,
    }
    assert {evidence.reviewed_on for evidence in filosax.evidence} == {"2026-07-23"}


def test_catalog_load_is_offline_and_contains_no_dataset_payload_files() -> None:
    registry = load_dataset_registry(REGISTRY_PATH)

    assert registry.datasets[0].dataset_id == "filosax"
    tracked_suffixes = {
        path.suffix.lower()
        for path in REGISTRY_PATH.parent.rglob("*")
        if path.is_file()
    }
    assert tracked_suffixes == {".json"}
