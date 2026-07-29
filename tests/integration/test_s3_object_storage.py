from __future__ import annotations

import urllib.request

import pytest

from saxo_ai.infrastructure.object_storage_configuration import ObjectStorageSettings
from saxo_ai.infrastructure.s3_object_storage import S3ObjectStorage

pytestmark = pytest.mark.object_storage_integration


class TestS3ObjectStorage:
    def test_put_then_get_round_trips(self, object_storage_settings: ObjectStorageSettings) -> None:
        storage = S3ObjectStorage(object_storage_settings)

        storage.put("some/key.txt", b"hello world", content_type="text/plain")

        assert storage.get("some/key.txt") == b"hello world"

    def test_get_missing_key_returns_none(
        self, object_storage_settings: ObjectStorageSettings
    ) -> None:
        storage = S3ObjectStorage(object_storage_settings)

        assert storage.get("does/not/exist.txt") is None

    def test_generate_presigned_get_url_is_usable(
        self, object_storage_settings: ObjectStorageSettings
    ) -> None:
        storage = S3ObjectStorage(object_storage_settings)
        storage.put("presigned/key.txt", b"presigned content", content_type="text/plain")

        url = storage.generate_presigned_get_url("presigned/key.txt", expires_in_seconds=60)

        with urllib.request.urlopen(url) as response:
            assert response.read() == b"presigned content"

    def test_generate_presigned_get_url_rejects_non_positive_expiry(
        self, object_storage_settings: ObjectStorageSettings
    ) -> None:
        storage = S3ObjectStorage(object_storage_settings)

        with pytest.raises(ValueError, match="expires_in_seconds"):
            storage.generate_presigned_get_url("some/key.txt", expires_in_seconds=0)
