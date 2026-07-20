import hashlib

from saxo_ai.application.errors import AudioSizeLimitExceededError
from saxo_ai.application.ports import BinaryStream
from saxo_ai.domain.audio import DEFAULT_MAX_AUDIO_SIZE_BYTES
from saxo_ai.domain.models import AudioContentMetadata

DEFAULT_CHUNK_SIZE = 64 * 1024


class Sha256AudioContentHasher:
    def __init__(
        self,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        max_size_bytes: int = DEFAULT_MAX_AUDIO_SIZE_BYTES,
    ) -> None:
        if isinstance(chunk_size, bool) or not isinstance(chunk_size, int):
            raise TypeError("chunk_size must be an integer")
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero")
        if isinstance(max_size_bytes, bool) or not isinstance(max_size_bytes, int):
            raise TypeError("max_size_bytes must be an integer")
        if max_size_bytes <= 0:
            raise ValueError("max_size_bytes must be greater than zero")
        self._chunk_size = chunk_size
        self._max_size_bytes = max_size_bytes

    def inspect(self, stream: BinaryStream) -> AudioContentMetadata:
        digest = hashlib.sha256()
        size_bytes = 0

        while True:
            remaining_until_rejection = self._max_size_bytes - size_bytes + 1
            read_size = min(self._chunk_size, remaining_until_rejection)
            chunk = stream.read(read_size)
            if chunk == b"":
                break

            size_bytes += len(chunk)
            if size_bytes > self._max_size_bytes:
                raise AudioSizeLimitExceededError(
                    max_size_bytes=self._max_size_bytes,
                    observed_size_bytes=size_bytes,
                )
            digest.update(chunk)

        return AudioContentMetadata(
            size_bytes=size_bytes,
            audio_sha256=digest.hexdigest(),
        )
