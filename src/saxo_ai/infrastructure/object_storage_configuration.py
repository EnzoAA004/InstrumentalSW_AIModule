from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

ENDPOINT_URL_ENV = "SAXO_OBJECT_STORAGE_ENDPOINT_URL"
BUCKET_ENV = "SAXO_OBJECT_STORAGE_BUCKET"
ACCESS_KEY_ENV = "SAXO_OBJECT_STORAGE_ACCESS_KEY"
SECRET_KEY_ENV = "SAXO_OBJECT_STORAGE_SECRET_KEY"
REGION_ENV = "SAXO_OBJECT_STORAGE_REGION"
DEFAULT_REGION = "us-east-1"


class ObjectStorageConfigurationError(ValueError):
    """Raised when object-storage connection configuration is missing or malformed."""


@dataclass(frozen=True, slots=True)
class ObjectStorageSettings:
    endpoint_url: str
    bucket: str
    access_key: str
    secret_key: str
    region: str


def load_object_storage_settings(
    environ: Mapping[str, str] | None = None,
) -> ObjectStorageSettings:
    """Read private object-storage connection settings; no default bucket or credentials."""

    values = os.environ if environ is None else environ
    return ObjectStorageSettings(
        endpoint_url=_require(values, ENDPOINT_URL_ENV),
        bucket=_require(values, BUCKET_ENV),
        access_key=_require(values, ACCESS_KEY_ENV),
        secret_key=_require(values, SECRET_KEY_ENV),
        region=values.get(REGION_ENV) or DEFAULT_REGION,
    )


def _require(values: Mapping[str, str], env_name: str) -> str:
    raw = values.get(env_name)
    if raw is None or not raw.strip():
        raise ObjectStorageConfigurationError(f"{env_name} must be set")
    return raw
