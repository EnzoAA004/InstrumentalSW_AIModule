from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    UniqueConstraint,
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

transcription_processing_queue = Table(
    "transcription_processing_queue",
    metadata,
    Column(
        "job_id",
        PostgresUUID(as_uuid=True),
        ForeignKey("transcription_jobs.job_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("attempt_count", Integer, nullable=False),
    Column("available_at", DateTime(timezone=True), nullable=False),
    Column("claimed_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
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

transcription_reviews = Table(
    "transcription_reviews",
    metadata,
    Column(
        "job_id",
        PostgresUUID(as_uuid=True),
        ForeignKey("transcription_jobs.job_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("saxophone_type", String(16), nullable=False),
    Column("low_confidence_threshold", Float, nullable=False),
    Column("confidence_method", String, nullable=False),
    Column("engine_name", String, nullable=False),
    Column("engine_version", String, nullable=False),
    Column("engine_source_revision", String(40), nullable=False),
    Column("model_id", String, nullable=False),
    Column("model_revision", String, nullable=False),
    Column("checkpoint_filename", String, nullable=False),
    Column("checkpoint_sha256", String(64), nullable=False),
    Column("sample_rate_hz", Integer, nullable=False),
    Column("device", String, nullable=False),
    Column("onset_threshold", Float, nullable=False),
    Column("offset_threshold", Float, nullable=False),
    Column("frame_threshold", Float, nullable=False),
    CheckConstraint("low_confidence_threshold >= 0.0 and low_confidence_threshold <= 1.0"),
    CheckConstraint("sample_rate_hz > 0"),
)

transcription_review_events = Table(
    "transcription_review_events",
    metadata,
    Column(
        "job_id",
        PostgresUUID(as_uuid=True),
        ForeignKey("transcription_reviews.job_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("event_index", Integer, nullable=False),
    Column("pitch_concert_midi", Integer, nullable=False),
    Column("written_pitch_midi", Integer, nullable=False),
    Column("onset_seconds", Float, nullable=False),
    Column("offset_seconds", Float, nullable=False),
    Column("velocity", Integer, nullable=False),
    Column("confidence", Float, nullable=False),
    Column("is_low_confidence", Boolean, nullable=False),
    PrimaryKeyConstraint("job_id", "event_index"),
    CheckConstraint("event_index >= 0"),
    CheckConstraint("pitch_concert_midi >= 0 and pitch_concert_midi <= 127"),
    CheckConstraint("written_pitch_midi >= 0 and written_pitch_midi <= 127"),
    CheckConstraint("onset_seconds >= 0.0"),
    CheckConstraint("offset_seconds > onset_seconds"),
    CheckConstraint("velocity >= 0 and velocity <= 127"),
    CheckConstraint("confidence >= 0.0 and confidence <= 1.0"),
)

transcription_revisions = Table(
    "transcription_revisions",
    metadata,
    Column(
        "job_id",
        PostgresUUID(as_uuid=True),
        ForeignKey("transcription_jobs.job_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("revision_number", Integer, nullable=False),
    Column("parent_revision_number", Integer, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("saxophone_type", String(16), nullable=False),
    Column("derived_artifacts_status", String(32), nullable=False),
    PrimaryKeyConstraint("job_id", "revision_number"),
    CheckConstraint("revision_number >= 0"),
    CheckConstraint(
        "(revision_number = 0 and parent_revision_number is null) or "
        "(revision_number > 0 and parent_revision_number = revision_number - 1)"
    ),
)

transcription_revision_events = Table(
    "transcription_revision_events",
    metadata,
    Column("job_id", PostgresUUID(as_uuid=True), nullable=False),
    Column("revision_number", Integer, nullable=False),
    Column("event_id", String, nullable=False),
    Column("order_index", Integer, nullable=False),
    Column("origin", String(16), nullable=False),
    Column("source_index", Integer, nullable=True),
    Column("pitch_concert_midi", Integer, nullable=False),
    Column("written_pitch_midi", Integer, nullable=False),
    Column("onset_seconds", Float, nullable=False),
    Column("offset_seconds", Float, nullable=False),
    Column("velocity", Integer, nullable=False),
    Column("confidence", Float, nullable=True),
    Column("is_low_confidence", Boolean, nullable=True),
    PrimaryKeyConstraint("job_id", "revision_number", "event_id"),
    UniqueConstraint("job_id", "revision_number", "order_index"),
    ForeignKeyConstraint(
        ["job_id", "revision_number"],
        ["transcription_revisions.job_id", "transcription_revisions.revision_number"],
        ondelete="CASCADE",
    ),
    CheckConstraint("order_index >= 0"),
    CheckConstraint("origin in ('model', 'human')"),
    CheckConstraint("pitch_concert_midi >= 0 and pitch_concert_midi <= 127"),
    CheckConstraint("written_pitch_midi >= 0 and written_pitch_midi <= 127"),
    CheckConstraint("onset_seconds >= 0.0"),
    CheckConstraint("offset_seconds > onset_seconds"),
    CheckConstraint("velocity >= 0 and velocity <= 127"),
    CheckConstraint("confidence is null or (confidence >= 0.0 and confidence <= 1.0)"),
)

regeneration_requests = Table(
    "regeneration_requests",
    metadata,
    Column("request_id", PostgresUUID(as_uuid=True), primary_key=True),
    Column("job_id", PostgresUUID(as_uuid=True), nullable=False),
    Column("revision_number", Integer, nullable=False),
    Column("status", String(16), nullable=False),
    Column("requested_artifacts", String, nullable=False),
    Column("requested_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("job_id", "revision_number"),
    ForeignKeyConstraint(
        ["job_id", "revision_number"],
        ["transcription_revisions.job_id", "transcription_revisions.revision_number"],
        ondelete="CASCADE",
    ),
    CheckConstraint("status = 'REQUESTED'"),
)

Index(
    "ix_transcription_revision_events_job_revision",
    transcription_revision_events.c.job_id,
    transcription_revision_events.c.revision_number,
)
