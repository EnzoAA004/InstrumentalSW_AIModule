from __future__ import annotations

from typing import Protocol, runtime_checkable

from saxo_ai.application.ports import BinaryStream
from saxo_ai.domain.transcription import TranscriptionResult


@runtime_checkable
class TranscriptionEngine(Protocol):
    def transcribe(self, source: BinaryStream) -> TranscriptionResult: ...


class TranscribeCanonicalAudio:
    """Delegate canonical audio transcription to a replaceable engine port."""

    def __init__(self, engine: TranscriptionEngine) -> None:
        self._engine = engine

    def execute(self, source: BinaryStream) -> TranscriptionResult:
        return self._engine.transcribe(source)
