from __future__ import annotations

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from saxo_ai.infrastructure.object_storage_configuration import ObjectStorageSettings

_MISSING_KEY_ERROR_CODES = frozenset({"NoSuchKey", "404"})


class S3ObjectStorage:
    """ObjectStorage backed by any S3-compatible endpoint (private MinIO or AWS S3)."""

    def __init__(self, settings: ObjectStorageSettings) -> None:
        self._bucket = settings.bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.endpoint_url,
            aws_access_key_id=settings.access_key,
            aws_secret_access_key=settings.secret_key,
            region_name=settings.region,
            config=Config(signature_version="s3v4"),
        )

    def put(self, key: str, content: bytes, *, content_type: str) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )

    def get(self, key: str) -> bytes | None:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in _MISSING_KEY_ERROR_CODES:
                return None
            raise
        return response["Body"].read()

    def generate_presigned_get_url(self, key: str, *, expires_in_seconds: int) -> str:
        if expires_in_seconds <= 0:
            raise ValueError("expires_in_seconds must be greater than zero")
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in_seconds,
        )
