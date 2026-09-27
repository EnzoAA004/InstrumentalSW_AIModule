from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
)
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

revision_artifact_bundles = Table(
    "revision_artifact_bundles",
    metadata,
    Column("job_id", PostgresUUID(as_uuid=True), nullable=False),
    Column("revision_number", Integer, nullable=False),
    PrimaryKeyConstraint("job_id", "revision_number"),
)

revision_artifacts = Table(
    "revision_artifacts",
    metadata,
    Column("job_id", PostgresUUID(as_uuid=True), nullable=False),
    Column("revision_number", Integer, nullable=False),
    Column("artifact_id", String(64), nullable=False),
    Column("artifact_type", String(16), nullable=False),
    Column("filename", String, nullable=False),
    Column("media_type", String, nullable=False),
    Column("extension", String(16), nullable=False),
    Column("size_bytes", BigInteger, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("order_index", Integer, nullable=False),
    Column("storage_key", String, nullable=False),
    PrimaryKeyConstraint("job_id", "revision_number", "artifact_id"),
    ForeignKeyConstraint(
        ["job_id", "revision_number"],
        ["revision_artifact_bundles.job_id", "revision_artifact_bundles.revision_number"],
    ),
)
