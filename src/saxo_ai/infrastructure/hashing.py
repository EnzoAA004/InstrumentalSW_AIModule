import hashlib

from saxo_ai.application.ports import BinaryStream
from saxo_ai.domain.models import AudioContentMetadata

DEFAULT_CHUNK_SIZE = 64 * 1024


class Sha256AudioContentHasher:
    def __init__(self, *, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero")
        self._chunk_size = chunk_size

    def inspect(self, stream: BinaryStream) -> AudioContentMetadata:
        digest = hashlib.sha256()
        size_bytes = 0

        while True:
            chunk = stream.read(self._chunk_size)
            if chunk == b"":
                break
            digest.update(chunk)
            size_bytes += len(chunk)

        return AudioContentMetadata(
            size_bytes=size_bytes,
            audio_sha256=digest.hexdigest(),
        )
