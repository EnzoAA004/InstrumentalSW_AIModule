from __future__ import annotations

import pytest

from saxo_ai.infrastructure.object_storage_configuration import (
    ACCESS_KEY_ENV,
    BUCKET_ENV,
    DEFAULT_REGION,
    ENDPOINT_URL_ENV,
    REGION_ENV,
    SECRET_KEY_ENV,
    ObjectStorageConfigurationError,
    load_object_storage_settings,
)

VALID_ENV = {
    ENDPOINT_URL_ENV: "https://storage.internal:9000",
    BUCKET_ENV: "saxo-artifacts",
    ACCESS_KEY_ENV: "access",
    SECRET_KEY_ENV: "secret",
}


class TestLoadObjectStorageSettings:
    def test_reads_all_configured_values(self) -> None:
        settings = load_object_storage_settings({**VALID_ENV, REGION_ENV: "eu-west-1"})

        assert settings.endpoint_url == "https://storage.internal:9000"
        assert settings.bucket == "saxo-artifacts"
        assert settings.access_key == "access"
        assert settings.secret_key == "secret"
        assert settings.region == "eu-west-1"

    def test_defaults_region_when_unset(self) -> None:
        settings = load_object_storage_settings(VALID_ENV)

        assert settings.region == DEFAULT_REGION

    @pytest.mark.parametrize(
        "missing_env", [ENDPOINT_URL_ENV, BUCKET_ENV, ACCESS_KEY_ENV, SECRET_KEY_ENV]
    )
    def test_rejects_missing_required_variable(self, missing_env: str) -> None:
        incomplete = {key: value for key, value in VALID_ENV.items() if key != missing_env}
        with pytest.raises(ObjectStorageConfigurationError):
            load_object_storage_settings(incomplete)

    def test_rejects_blank_required_variable(self) -> None:
        with pytest.raises(ObjectStorageConfigurationError):
            load_object_storage_settings({**VALID_ENV, BUCKET_ENV: "   "})
