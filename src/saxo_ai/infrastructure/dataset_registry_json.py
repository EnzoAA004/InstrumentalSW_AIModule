from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import TypeVar

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

_EnumValue = TypeVar("_EnumValue", bound=StrEnum)

_REGISTRY_FIELDS = frozenset({"schema_version", "datasets"})
_DATASET_FIELDS = frozenset(
    {
        "dataset_id",
        "title",
        "creators",
        "publisher",
        "release_reference",
        "canonical_uri",
        "doi",
        "access_mode",
        "license",
        "use_rules",
        "evidence",
    }
)
_LICENSE_FIELDS = frozenset(
    {
        "kind",
        "identifier",
        "title",
        "terms_uri",
        "attribution_required",
        "required_citation",
        "terms_may_change",
    }
)
_USE_RULE_FIELDS = frozenset({"use", "decision", "conditions"})
_EVIDENCE_FIELDS = frozenset({"kind", "uri", "reviewed_on"})


class InvalidDatasetRegistryJsonError(ValueError):
    """Raised when JSON cannot be decoded into the exact registry schema."""


def load_dataset_registry(path: Path) -> DatasetRegistry:
    """Load one UTF-8 JSON registry using exact fields and immutable domain contracts."""

    if not isinstance(path, Path):
        raise InvalidDatasetRegistryJsonError("registry path must be pathlib.Path")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise InvalidDatasetRegistryJsonError(
            "registry file could not be read as UTF-8"
        ) from error
    try:
        parsed: object = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as error:
        raise InvalidDatasetRegistryJsonError(
            "registry file must contain valid JSON"
        ) from error
    try:
        return _decode_registry(parsed)
    except InvalidDatasetProvenanceError as error:
        raise InvalidDatasetRegistryJsonError(str(error)) from error


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidDatasetRegistryJsonError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _decode_registry(value: object) -> DatasetRegistry:
    payload = _require_object(value, "registry")
    _require_exact_fields(payload, _REGISTRY_FIELDS, "registry")
    schema_version = _require_string(payload["schema_version"], "schema_version")
    if schema_version != DATASET_REGISTRY_SCHEMA_VERSION:
        raise InvalidDatasetRegistryJsonError(
            f"schema_version must be {DATASET_REGISTRY_SCHEMA_VERSION}"
        )
    datasets = tuple(
        _decode_dataset(item, index)
        for index, item in enumerate(_require_list(payload["datasets"], "datasets"))
    )
    return DatasetRegistry(schema_version=schema_version, datasets=datasets)


def _decode_dataset(value: object, index: int) -> DatasetProvenanceRecord:
    context = f"datasets[{index}]"
    payload = _require_object(value, context)
    _require_exact_fields(payload, _DATASET_FIELDS, context)
    creators = tuple(
        _require_string(item, f"{context}.creators[{creator_index}]")
        for creator_index, item in enumerate(
            _require_list(payload["creators"], f"{context}.creators")
        )
    )
    use_rules = tuple(
        _decode_use_rule(item, f"{context}.use_rules[{rule_index}]")
        for rule_index, item in enumerate(
            _require_list(payload["use_rules"], f"{context}.use_rules")
        )
    )
    evidence = tuple(
        _decode_evidence(item, f"{context}.evidence[{evidence_index}]")
        for evidence_index, item in enumerate(
            _require_list(payload["evidence"], f"{context}.evidence")
        )
    )
    return DatasetProvenanceRecord(
        dataset_id=_require_string(payload["dataset_id"], f"{context}.dataset_id"),
        title=_require_string(payload["title"], f"{context}.title"),
        creators=creators,
        publisher=_require_string(payload["publisher"], f"{context}.publisher"),
        release_reference=_require_string(
            payload["release_reference"], f"{context}.release_reference"
        ),
        canonical_uri=_require_string(
            payload["canonical_uri"], f"{context}.canonical_uri"
        ),
        doi=_require_string(payload["doi"], f"{context}.doi"),
        access_mode=_decode_enum(
            DatasetAccessMode,
            payload["access_mode"],
            f"{context}.access_mode",
        ),
        license=_decode_license(payload["license"], f"{context}.license"),
        use_rules=use_rules,
        evidence=evidence,
    )


def _decode_license(value: object, context: str) -> DatasetLicense:
    payload = _require_object(value, context)
    _require_exact_fields(payload, _LICENSE_FIELDS, context)
    return DatasetLicense(
        kind=_decode_enum(DatasetLicenseKind, payload["kind"], f"{context}.kind"),
        identifier=_require_string(payload["identifier"], f"{context}.identifier"),
        title=_require_string(payload["title"], f"{context}.title"),
        terms_uri=_require_string(payload["terms_uri"], f"{context}.terms_uri"),
        attribution_required=_require_bool(
            payload["attribution_required"], f"{context}.attribution_required"
        ),
        required_citation=_require_string(
            payload["required_citation"],
            f"{context}.required_citation",
            allow_empty=True,
        ),
        terms_may_change=_require_bool(
            payload["terms_may_change"], f"{context}.terms_may_change"
        ),
    )


def _decode_use_rule(value: object, context: str) -> DatasetUseRule:
    payload = _require_object(value, context)
    _require_exact_fields(payload, _USE_RULE_FIELDS, context)
    conditions = tuple(
        _require_string(item, f"{context}.conditions[{condition_index}]")
        for condition_index, item in enumerate(
            _require_list(payload["conditions"], f"{context}.conditions")
        )
    )
    return DatasetUseRule(
        use=_decode_enum(DatasetUse, payload["use"], f"{context}.use"),
        decision=_decode_enum(
            DatasetUseDecision,
            payload["decision"],
            f"{context}.decision",
        ),
        conditions=conditions,
    )


def _decode_evidence(value: object, context: str) -> DatasetEvidence:
    payload = _require_object(value, context)
    _require_exact_fields(payload, _EVIDENCE_FIELDS, context)
    return DatasetEvidence(
        kind=_decode_enum(DatasetEvidenceKind, payload["kind"], f"{context}.kind"),
        uri=_require_string(payload["uri"], f"{context}.uri"),
        reviewed_on=_require_string(
            payload["reviewed_on"], f"{context}.reviewed_on"
        ),
    )


def _require_object(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise InvalidDatasetRegistryJsonError(f"{context} must be an object")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise InvalidDatasetRegistryJsonError(f"{context} keys must be strings")
        result[key] = item
    return result


def _require_list(value: object, context: str) -> list[object]:
    if not isinstance(value, list):
        raise InvalidDatasetRegistryJsonError(f"{context} must be an array")
    return list(value)


def _require_string(
    value: object, context: str, *, allow_empty: bool = False
) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        qualifier = "a string" if allow_empty else "a non-empty string"
        raise InvalidDatasetRegistryJsonError(f"{context} must be {qualifier}")
    return value


def _require_bool(value: object, context: str) -> bool:
    if not isinstance(value, bool):
        raise InvalidDatasetRegistryJsonError(f"{context} must be a boolean")
    return value


def _require_exact_fields(
    payload: dict[str, object], expected: frozenset[str], context: str
) -> None:
    actual = frozenset(payload)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise InvalidDatasetRegistryJsonError(
            f"{context} is missing fields: {', '.join(sorted(missing))}"
        )
    if unknown:
        raise InvalidDatasetRegistryJsonError(
            f"{context} contains unknown fields: {', '.join(sorted(unknown))}"
        )


def _decode_enum(
    enum_type: type[_EnumValue], value: object, context: str
) -> _EnumValue:
    text = _require_string(value, context)
    try:
        return enum_type(text)
    except ValueError as error:
        raise InvalidDatasetRegistryJsonError(
            f"{context} contains an unknown value"
        ) from error
