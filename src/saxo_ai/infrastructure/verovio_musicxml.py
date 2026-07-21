from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

import verovio

from saxo_ai.application.musicxml_export import MusicXmlReaderError, MusicXmlValidationError
from saxo_ai.domain.musicxml_export import MusicXmlValidationSummary


def _summarize_log(value: object) -> str:
    if not isinstance(value, str):
        return ""
    compact = " ".join(value.split())
    return compact[:300]


def _configured_toolkit() -> Any:
    enable_log_to_buffer = getattr(verovio, "enableLogToBuffer", None)
    if callable(enable_log_to_buffer):
        enable_log_to_buffer(True)
    verovio.enableLog(verovio.LOG_ERROR)
    toolkit = verovio.toolkit()
    toolkit.setOptions({"inputFrom": "xml", "xmlIdSeed": 0})
    return toolkit


class VerovioMusicXmlReader:
    def validate(self, *, content: bytes) -> MusicXmlValidationSummary:
        if not isinstance(content, bytes) or not content:
            raise MusicXmlReaderError("MusicXML reader requires non-empty bytes.")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise MusicXmlReaderError("MusicXML reader requires UTF-8 content.") from error
        try:
            root = ET.fromstring(text)
        except ET.ParseError as error:
            raise MusicXmlReaderError("MusicXML content is not well formed.") from error

        toolkit = _configured_toolkit()
        try:
            loaded = bool(toolkit.loadData(text))
        except Exception as error:
            raise MusicXmlReaderError("External MusicXML reader failed.") from error
        if not loaded:
            log = _summarize_log(toolkit.getLog())
            suffix = f" Reader log: {log}" if log else ""
            raise MusicXmlValidationError(f"External reader rejected MusicXML.{suffix}")
        try:
            mei = toolkit.getMEI()
        except Exception as error:
            raise MusicXmlReaderError("External reader could not expose imported data.") from error
        if not isinstance(mei, str) or not mei.strip() or "<mei" not in mei:
            raise MusicXmlValidationError("External reader returned no imported representation.")

        notes = root.findall("./part/measure/note")
        rest_count = sum(note.find("rest") is not None for note in notes)
        return MusicXmlValidationSummary(
            document_version=root.attrib.get("version", ""),
            part_count=len(root.findall("./part")),
            measure_count=len(root.findall("./part/measure")),
            note_segment_count=len(notes) - rest_count,
            rest_segment_count=rest_count,
            loaded_by_external_reader=True,
        )
