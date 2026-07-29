from __future__ import annotations

from sqlalchemy import BigInteger, Column, MetaData, String, Table
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

metadata = MetaData()

transcription_jobs = Table(
    "transcription_jobs",
    metadata,
    Column("job_id", PostgresUUID(as_uuid=True), primary_key=True),
    Column("status", String(16), nullable=False),
    Column("filename", String, nullable=False),
    Column("size_bytes", BigInteger, nullable=False),
    Column("audio_sha256", String(64), nullable=False),
    Column("saxophone_type", String(16), nullable=False),
    Column("input_mode", String(16), nullable=False),
    Column("failure_code", String(64), nullable=True),
)
