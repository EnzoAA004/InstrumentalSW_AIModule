from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from saxo_ai.domain.dataset_provenance import DatasetUse, DatasetUseDecision
from saxo_ai.infrastructure.dataset_registry_json import (
    InvalidDatasetRegistryJsonError,
    load_dataset_registry,
)


def evidence_payload(kind: str = "official_documentation") -> dict[str, object]:
    return {
        "kind": kind,
        "uri": "https://example.org/dataset/terms",
        "reviewed_on": "2026-07-23",
    }


def license_payload() -> dict[str, object]:
    return {
        "kind": "custom",
        "identifier": "example-custom-terms",
        "title": "Example restricted dataset terms",
        "terms_uri": "https://example.org/dataset/terms",
        "attribution_required": True,
        "required_citation": "Example Dataset citation.",
        "terms_may_change": True,
    }


def use_rules_payload() -> list[object]:
    decisions = {
        "download": "requires_permission",
        "internal_noncommercial_research": "allowed_with_conditions",
        "commercial_use": "prohibited",
        "redistribution": "prohibited",
        "reproduction_material_distribution": "prohibited",
        "publication_of_results": "allowed_with_conditions",
        "derived_asset_distribution": "not_stated",
    }
    return [
        {
            "use": use,
            "decision": decision,
            "conditions": [] if decision == "not_stated" else ["Follow official terms."],
        }
        for use, decision in decisions.items()
    ]


def dataset_payload(dataset_id: str = "example-dataset") -> dict[str, object]:
    return {
        "dataset_id": dataset_id,
        "title": "Example Dataset",
        "creators": ["Researcher One", "Researcher Two"],
        "publisher": "Example Repository",
        "release_reference": "repository-record-123",
        "canonical_uri": "https://example.org/records/123",
        "doi": "10.1234/example.123",
        "access_mode": "restricted",
        "license": license_payload(),
        "use_rules": use_rules_payload(),
        "evidence": [evidence_payload()],
    }


def registry_payload() -> dict[str, object]:
    return {"schema_version": "1.0", "datasets": [dataset_payload()]}


def write_payload(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def require_object(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    assert all(isinstance(key, str) for key in value)
    return cast(dict[str, object], value)


def require_list(value: object) -> list[object]:
    assert isinstance(value, list)
    return cast(list[object], value)


def first_dataset(payload: dict[str, object]) -> dict[str, object]:
    datasets = require_list(payload["datasets"])
    assert datasets
    return require_object(datasets[0])


def nested_object(parent: dict[str, object], key: str) -> dict[str, object]:
    return require_object(parent[key])


def nested_list(parent: dict[str, object], key: str) -> list[object]:
    return require_list(parent[key])


def test_loader_builds_immutable_domain_contracts_from_exact_versioned_json(
    tmp_path: Path,
) -> None:
    registry = load_dataset_registry(write_payload(tmp_path, registry_payload()))

    assert registry.schema_version == "1.0"
    assert registry.datasets[0].dataset_id == "example-dataset"
    assert registry.datasets[0].creators == ("Researcher One", "Researcher Two")
    assert isinstance(registry.datasets[0].creators, tuple)
    assert tuple(rule.use for rule in registry.datasets[0].use_rules) == tuple(DatasetUse)
    assert registry.datasets[0].use_rules[-1].decision is DatasetUseDecision.NOT_STATED


@pytest.mark.parametrize(
    "payload",
    [
        {"datasets": [dataset_payload()]},
        {"schema_version": "2.0", "datasets": [dataset_payload()]},
        {"schema_version": None, "datasets": [dataset_payload()]},
        {"schema_version": "1.0", "datasets": []},
        {"schema_version": "1.0", "datasets": "not-a-list"},
        {"schema_version": "1.0", "datasets": [dataset_payload(), dataset_payload()]},
        {
            "schema_version": "1.0",
            "datasets": [dataset_payload("second"), dataset_payload("first")],
        },
    ],
)
def test_loader_rejects_missing_future_or_invalid_registry_shapes(
    tmp_path: Path, payload: object
) -> None:
    with pytest.raises(InvalidDatasetRegistryJsonError):
        load_dataset_registry(write_payload(tmp_path, payload))


def test_loader_rejects_unknown_top_level_and_dataset_fields(tmp_path: Path) -> None:
    top = registry_payload()
    top["unexpected"] = "value"
    with pytest.raises(InvalidDatasetRegistryJsonError):
        load_dataset_registry(write_payload(tmp_path, top))

    internal = registry_payload()
    first_dataset(internal)["unexpected"] = "value"
    with pytest.raises(InvalidDatasetRegistryJsonError):
        load_dataset_registry(write_payload(tmp_path, internal))


def test_loader_rejects_missing_dataset_and_nested_fields(tmp_path: Path) -> None:
    missing_dataset = registry_payload()
    first_dataset(missing_dataset).pop("publisher")
    with pytest.raises(InvalidDatasetRegistryJsonError):
        load_dataset_registry(write_payload(tmp_path, missing_dataset))

    missing_license = registry_payload()
    nested_object(first_dataset(missing_license), "license").pop("terms_uri")
    with pytest.raises(InvalidDatasetRegistryJsonError):
        load_dataset_registry(write_payload(tmp_path, missing_license))

    missing_rule = registry_payload()
    rule = require_object(nested_list(first_dataset(missing_rule), "use_rules")[0])
    rule.pop("decision")
    with pytest.raises(InvalidDatasetRegistryJsonError):
        load_dataset_registry(write_payload(tmp_path, missing_rule))

    missing_evidence = registry_payload()
    evidence = require_object(nested_list(first_dataset(missing_evidence), "evidence")[0])
    evidence.pop("reviewed_on")
    with pytest.raises(InvalidDatasetRegistryJsonError):
        load_dataset_registry(write_payload(tmp_path, missing_evidence))


def test_loader_rejects_unknown_nested_fields_and_enum_values(tmp_path: Path) -> None:
    unknown_license = registry_payload()
    nested_object(first_dataset(unknown_license), "license")["unexpected"] = True
    with pytest.raises(InvalidDatasetRegistryJsonError):
        load_dataset_registry(write_payload(tmp_path, unknown_license))

    unknown_evidence = registry_payload()
    evidence = require_object(nested_list(first_dataset(unknown_evidence), "evidence")[0])
    evidence["kind"] = "blog"
    with pytest.raises(InvalidDatasetRegistryJsonError):
        load_dataset_registry(write_payload(tmp_path, unknown_evidence))

    unknown_decision = registry_payload()
    rule = require_object(nested_list(first_dataset(unknown_decision), "use_rules")[0])
    rule["decision"] = "maybe"
    with pytest.raises(InvalidDatasetRegistryJsonError):
        load_dataset_registry(write_payload(tmp_path, unknown_decision))


def test_loader_rejects_incorrect_scalar_and_collection_types(tmp_path: Path) -> None:
    wrong_creators = registry_payload()
    first_dataset(wrong_creators)["creators"] = "Researcher One"
    with pytest.raises(InvalidDatasetRegistryJsonError):
        load_dataset_registry(write_payload(tmp_path, wrong_creators))

    wrong_boolean = registry_payload()
    nested_object(first_dataset(wrong_boolean), "license")["terms_may_change"] = 1
    with pytest.raises(InvalidDatasetRegistryJsonError):
        load_dataset_registry(write_payload(tmp_path, wrong_boolean))

    wrong_conditions = registry_payload()
    rule = require_object(nested_list(first_dataset(wrong_conditions), "use_rules")[0])
    rule["conditions"] = "permission required"
    with pytest.raises(InvalidDatasetRegistryJsonError):
        load_dataset_registry(write_payload(tmp_path, wrong_conditions))


def test_loader_rejects_duplicate_rules_and_json_object_keys(tmp_path: Path) -> None:
    duplicate_rule = registry_payload()
    rules = nested_list(first_dataset(duplicate_rule), "use_rules")
    rules[-1] = rules[0]
    with pytest.raises(InvalidDatasetRegistryJsonError):
        load_dataset_registry(write_payload(tmp_path, duplicate_rule))

    duplicate_key = tmp_path / "duplicate-key.json"
    duplicate_key.write_text(
        '{"schema_version":"1.0","schema_version":"1.0","datasets":[]}',
        encoding="utf-8",
    )
    with pytest.raises(InvalidDatasetRegistryJsonError):
        load_dataset_registry(duplicate_key)


def test_loader_rejects_malformed_json_and_missing_files(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not-json", encoding="utf-8")
    with pytest.raises(InvalidDatasetRegistryJsonError):
        load_dataset_registry(malformed)
    with pytest.raises(InvalidDatasetRegistryJsonError):
        load_dataset_registry(tmp_path / "missing.json")
