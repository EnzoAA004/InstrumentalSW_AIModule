from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

DATASET_REGISTRY_SCHEMA_VERSION = "1.0"

_DATASET_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_CUSTOM_LICENSE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SPDX_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+-]*$")
_DOI = re.compile(r"^10\.[0-9]{4,9}/[-._;()/:A-Za-z0-9]+$")
_HTTPS_URI = re.compile(r"^https://([^/?#]+)([^\s]*)$")


class InvalidDatasetProvenanceError(ValueError):
    """Raised when dataset-governance metadata violates the versioned contract."""


class DatasetAccessMode(StrEnum):
    OPEN = "open"
    RESTRICTED = "restricted"
    CLOSED = "closed"
    PROJECT_GENERATED = "project_generated"


class DatasetLicenseKind(StrEnum):
    SPDX = "spdx"
    CUSTOM = "custom"


class DatasetUse(StrEnum):
    DOWNLOAD = "download"
    INTERNAL_NONCOMMERCIAL_RESEARCH = "internal_noncommercial_research"
    COMMERCIAL_USE = "commercial_use"
    REDISTRIBUTION = "redistribution"
    REPRODUCTION_MATERIAL_DISTRIBUTION = "reproduction_material_distribution"
    PUBLICATION_OF_RESULTS = "publication_of_results"
    DERIVED_ASSET_DISTRIBUTION = "derived_asset_distribution"


class DatasetUseDecision(StrEnum):
    ALLOWED = "allowed"
    ALLOWED_WITH_CONDITIONS = "allowed_with_conditions"
    PROHIBITED = "prohibited"
    REQUIRES_PERMISSION = "requires_permission"
    NOT_STATED = "not_stated"


class DatasetEvidenceKind(StrEnum):
    OFFICIAL_DOCUMENTATION = "official_documentation"
    REPOSITORY_RECORD = "repository_record"
    PAPER = "paper"


def _require_non_empty(field_name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidDatasetProvenanceError(f"{field_name} must be a non-empty string")
    return value


def _require_real_bool(field_name: str, value: object) -> bool:
    if not isinstance(value, bool):
        raise InvalidDatasetProvenanceError(f"{field_name} must be a boolean")
    return value


def _require_https_uri(field_name: str, value: object) -> str:
    uri = _require_non_empty(field_name, value)
    match = _HTTPS_URI.fullmatch(uri)
    if match is None or "\\" in uri:
        raise InvalidDatasetProvenanceError(f"{field_name} must be a safe HTTPS URI")
    authority, remainder = match.groups()
    if "@" in authority:
        raise InvalidDatasetProvenanceError(f"{field_name} must not contain credentials")
    hostname = authority.split(":", maxsplit=1)[0].lower()
    if (
        "." not in hostname
        or hostname == "localhost"
        or hostname.startswith("127.")
        or hostname in {"0.0.0.0", "::1", "[::1]"}
    ):
        raise InvalidDatasetProvenanceError(f"{field_name} must reference a public HTTPS host")
    path = remainder.split("?", maxsplit=1)[0].split("#", maxsplit=1)[0]
    if any(segment == ".." for segment in path.split("/")):
        raise InvalidDatasetProvenanceError(f"{field_name} must not contain path traversal")
    return uri


def _require_iso_date(field_name: str, value: object) -> str:
    text = _require_non_empty(field_name, value)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as error:
        raise InvalidDatasetProvenanceError(
            f"{field_name} must be an ISO date in YYYY-MM-DD form"
        ) from error
    if parsed.isoformat() != text:
        raise InvalidDatasetProvenanceError(
            f"{field_name} must be an ISO date in YYYY-MM-DD form"
        )
    return text


@dataclass(frozen=True, slots=True)
class DatasetEvidence:
    kind: DatasetEvidenceKind
    uri: str
    reviewed_on: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, DatasetEvidenceKind):
            raise InvalidDatasetProvenanceError("evidence kind is not supported")
        object.__setattr__(self, "uri", _require_https_uri("evidence uri", self.uri))
        object.__setattr__(
            self,
            "reviewed_on",
            _require_iso_date("evidence reviewed_on", self.reviewed_on),
        )


@dataclass(frozen=True, slots=True)
class DatasetUseRule:
    use: DatasetUse
    decision: DatasetUseDecision
    conditions: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.use, DatasetUse):
            raise InvalidDatasetProvenanceError("dataset use is not supported")
        if not isinstance(self.decision, DatasetUseDecision):
            raise InvalidDatasetProvenanceError("dataset use decision is not supported")
        if not isinstance(self.conditions, tuple):
            raise InvalidDatasetProvenanceError("conditions must be an immutable tuple")
        if any(not isinstance(value, str) or not value.strip() for value in self.conditions):
            raise InvalidDatasetProvenanceError("conditions must contain non-empty strings")
        if self.decision is DatasetUseDecision.NOT_STATED and self.conditions:
            raise InvalidDatasetProvenanceError(
                "not_stated must remain empty and must not imply permission"
            )
        if self.decision in {
            DatasetUseDecision.ALLOWED_WITH_CONDITIONS,
            DatasetUseDecision.REQUIRES_PERMISSION,
        } and not self.conditions:
            raise InvalidDatasetProvenanceError(
                "conditional and permission decisions must preserve their conditions"
            )


@dataclass(frozen=True, slots=True)
class DatasetLicense:
    kind: DatasetLicenseKind
    identifier: str
    title: str
    terms_uri: str
    attribution_required: bool
    required_citation: str
    terms_may_change: bool

    def __post_init__(self) -> None:
        if not isinstance(self.kind, DatasetLicenseKind):
            raise InvalidDatasetProvenanceError("license kind must be spdx or custom")
        identifier = _require_non_empty("license identifier", self.identifier)
        pattern = _SPDX_IDENTIFIER if self.kind is DatasetLicenseKind.SPDX else _CUSTOM_LICENSE_ID
        if pattern.fullmatch(identifier) is None:
            raise InvalidDatasetProvenanceError(
                "license identifier is incompatible with the declared license kind"
            )
        object.__setattr__(self, "identifier", identifier)
        object.__setattr__(self, "title", _require_non_empty("license title", self.title))
        object.__setattr__(
            self,
            "terms_uri",
            _require_https_uri("license terms_uri", self.terms_uri),
        )
        attribution_required = _require_real_bool(
            "license attribution_required", self.attribution_required
        )
        citation = self.required_citation
        if not isinstance(citation, str):
            raise InvalidDatasetProvenanceError("license required_citation must be a string")
        if attribution_required and not citation.strip():
            raise InvalidDatasetProvenanceError(
                "attribution_required requires a non-empty required_citation"
            )
        object.__setattr__(self, "attribution_required", attribution_required)
        object.__setattr__(self, "required_citation", citation)
        object.__setattr__(
            self,
            "terms_may_change",
            _require_real_bool("license terms_may_change", self.terms_may_change),
        )


@dataclass(frozen=True, slots=True)
class DatasetProvenanceRecord:
    dataset_id: str
    title: str
    creators: tuple[str, ...]
    publisher: str
    release_reference: str
    canonical_uri: str
    doi: str
    access_mode: DatasetAccessMode
    license: DatasetLicense
    use_rules: tuple[DatasetUseRule, ...]
    evidence: tuple[DatasetEvidence, ...]

    def __post_init__(self) -> None:
        dataset_id = _require_non_empty("dataset_id", self.dataset_id)
        if _DATASET_ID.fullmatch(dataset_id) is None:
            raise InvalidDatasetProvenanceError(
                "dataset_id must be a safe stable lowercase identifier"
            )
        object.__setattr__(self, "dataset_id", dataset_id)
        object.__setattr__(self, "title", _require_non_empty("title", self.title))
        if not isinstance(self.creators, tuple) or not self.creators:
            raise InvalidDatasetProvenanceError("creators must be a non-empty immutable tuple")
        if any(not isinstance(value, str) or not value.strip() for value in self.creators):
            raise InvalidDatasetProvenanceError("creators must contain non-empty strings")
        if len(set(self.creators)) != len(self.creators):
            raise InvalidDatasetProvenanceError("creators must not contain duplicates")
        object.__setattr__(self, "publisher", _require_non_empty("publisher", self.publisher))
        object.__setattr__(
            self,
            "release_reference",
            _require_non_empty("release_reference", self.release_reference),
        )
        object.__setattr__(
            self,
            "canonical_uri",
            _require_https_uri("canonical_uri", self.canonical_uri),
        )
        doi = _require_non_empty("doi", self.doi)
        if _DOI.fullmatch(doi) is None:
            raise InvalidDatasetProvenanceError("doi must be a DOI reference, not a URL")
        object.__setattr__(self, "doi", doi)
        if not isinstance(self.access_mode, DatasetAccessMode):
            raise InvalidDatasetProvenanceError("access_mode is not supported")
        if not isinstance(self.license, DatasetLicense):
            raise InvalidDatasetProvenanceError("license must be DatasetLicense")
        if not isinstance(self.use_rules, tuple) or any(
            not isinstance(rule, DatasetUseRule) for rule in self.use_rules
        ):
            raise InvalidDatasetProvenanceError("use_rules must contain DatasetUseRule values")
        expected_uses = tuple(DatasetUse)
        actual_uses = tuple(rule.use for rule in self.use_rules)
        if actual_uses != expected_uses:
            raise InvalidDatasetProvenanceError(
                "use_rules must contain every DatasetUse exactly once in deterministic order"
            )
        if not isinstance(self.evidence, tuple) or not self.evidence:
            raise InvalidDatasetProvenanceError("evidence must be a non-empty immutable tuple")
        if any(not isinstance(value, DatasetEvidence) for value in self.evidence):
            raise InvalidDatasetProvenanceError("evidence must contain DatasetEvidence values")
        evidence_keys = tuple((value.kind, value.uri) for value in self.evidence)
        if len(set(evidence_keys)) != len(evidence_keys):
            raise InvalidDatasetProvenanceError("evidence entries must be unique")


@dataclass(frozen=True, slots=True)
class DatasetRegistry:
    schema_version: str
    datasets: tuple[DatasetProvenanceRecord, ...]

    def __post_init__(self) -> None:
        if self.schema_version != DATASET_REGISTRY_SCHEMA_VERSION:
            raise InvalidDatasetProvenanceError(
                f"schema_version must be {DATASET_REGISTRY_SCHEMA_VERSION}"
            )
        if not isinstance(self.datasets, tuple) or not self.datasets:
            raise InvalidDatasetProvenanceError("datasets must be a non-empty immutable tuple")
        if any(not isinstance(value, DatasetProvenanceRecord) for value in self.datasets):
            raise InvalidDatasetProvenanceError(
                "datasets must contain DatasetProvenanceRecord values"
            )
        dataset_ids = tuple(value.dataset_id for value in self.datasets)
        if len(set(dataset_ids)) != len(dataset_ids):
            raise InvalidDatasetProvenanceError("dataset_id values must be unique")
        if dataset_ids != tuple(sorted(dataset_ids)):
            raise InvalidDatasetProvenanceError("datasets must be sorted by dataset_id")
