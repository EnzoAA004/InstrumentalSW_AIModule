from hashlib import sha256


def sha256_hex(content: bytes) -> str:
    """Return the canonical lowercase SHA-256 digest for immutable bytes."""

    return sha256(content).hexdigest()
