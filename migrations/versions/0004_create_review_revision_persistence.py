"""create transcription review, revision, and regeneration persistence

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-27 23:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transcription_reviews",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("saxophone_type", sa.String(length=16), nullable=False),
        sa.Column("low_confidence_threshold", sa.Float(), nullable=False),
        sa.Column("confidence_method", sa.String(), nullable=False),
        sa.Column("engine_name", sa.String(), nullable=False),
        sa.Column("engine_version", sa.String(), nullable=False),
        sa.Column("engine_source_revision", sa.String(length=40), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("model_revision", sa.String(), nullable=False),
        sa.Column("checkpoint_filename", sa.String(), nullable=False),
        sa.Column("checkpoint_sha256", sa.String(length=64), nullable=False),
        sa.Column("sample_rate_hz", sa.Integer(), nullable=False),
        sa.Column("device", sa.String(), nullable=False),
        sa.Column("onset_threshold", sa.Float(), nullable=False),
        sa.Column("offset_threshold", sa.Float(), nullable=False),
        sa.Column("frame_threshold", sa.Float(), nullable=False),
        sa.CheckConstraint("low_confidence_threshold >= 0.0 and low_confidence_threshold <= 1.0"),
        sa.CheckConstraint("sample_rate_hz > 0"),
        sa.ForeignKeyConstraint(["job_id"], ["transcription_jobs.job_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_table(
        "transcription_review_events",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_index", sa.Integer(), nullable=False),
        sa.Column("pitch_concert_midi", sa.Integer(), nullable=False),
        sa.Column("written_pitch_midi", sa.Integer(), nullable=False),
        sa.Column("onset_seconds", sa.Float(), nullable=False),
        sa.Column("offset_seconds", sa.Float(), nullable=False),
        sa.Column("velocity", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("is_low_confidence", sa.Boolean(), nullable=False),
        sa.CheckConstraint("event_index >= 0"),
        sa.CheckConstraint("pitch_concert_midi >= 0 and pitch_concert_midi <= 127"),
        sa.CheckConstraint("written_pitch_midi >= 0 and written_pitch_midi <= 127"),
        sa.CheckConstraint("onset_seconds >= 0.0"),
        sa.CheckConstraint("offset_seconds > onset_seconds"),
        sa.CheckConstraint("velocity >= 0 and velocity <= 127"),
        sa.CheckConstraint("confidence >= 0.0 and confidence <= 1.0"),
        sa.ForeignKeyConstraint(["job_id"], ["transcription_reviews.job_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id", "event_index"),
    )
    op.create_table(
        "transcription_revisions",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("parent_revision_number", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("saxophone_type", sa.String(length=16), nullable=False),
        sa.Column("derived_artifacts_status", sa.String(length=32), nullable=False),
        sa.CheckConstraint("revision_number >= 0"),
        sa.CheckConstraint(
            "(revision_number = 0 and parent_revision_number is null) or "
            "(revision_number > 0 and parent_revision_number = revision_number - 1)"
        ),
        sa.ForeignKeyConstraint(["job_id"], ["transcription_jobs.job_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id", "revision_number"),
    )
    op.create_table(
        "transcription_revision_events",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("source_index", sa.Integer(), nullable=True),
        sa.Column("pitch_concert_midi", sa.Integer(), nullable=False),
        sa.Column("written_pitch_midi", sa.Integer(), nullable=False),
        sa.Column("onset_seconds", sa.Float(), nullable=False),
        sa.Column("offset_seconds", sa.Float(), nullable=False),
        sa.Column("velocity", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("is_low_confidence", sa.Boolean(), nullable=True),
        sa.CheckConstraint("order_index >= 0"),
        sa.CheckConstraint("origin in ('model', 'human')"),
        sa.CheckConstraint("pitch_concert_midi >= 0 and pitch_concert_midi <= 127"),
        sa.CheckConstraint("written_pitch_midi >= 0 and written_pitch_midi <= 127"),
        sa.CheckConstraint("onset_seconds >= 0.0"),
        sa.CheckConstraint("offset_seconds > onset_seconds"),
        sa.CheckConstraint("velocity >= 0 and velocity <= 127"),
        sa.CheckConstraint("confidence is null or (confidence >= 0.0 and confidence <= 1.0)"),
        sa.ForeignKeyConstraint(
            ["job_id", "revision_number"],
            ["transcription_revisions.job_id", "transcription_revisions.revision_number"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("job_id", "revision_number", "event_id"),
        sa.UniqueConstraint("job_id", "revision_number", "order_index"),
    )
    op.create_index(
        "ix_transcription_revision_events_job_revision",
        "transcription_revision_events",
        ["job_id", "revision_number"],
    )
    op.create_table(
        "regeneration_requests",
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_artifacts", sa.String(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status = 'REQUESTED'"),
        sa.ForeignKeyConstraint(
            ["job_id", "revision_number"],
            ["transcription_revisions.job_id", "transcription_revisions.revision_number"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("request_id"),
        sa.UniqueConstraint("job_id", "revision_number"),
    )


def downgrade() -> None:
    op.drop_table("regeneration_requests")
    op.drop_index(
        "ix_transcription_revision_events_job_revision",
        table_name="transcription_revision_events",
    )
    op.drop_table("transcription_revision_events")
    op.drop_table("transcription_revisions")
    op.drop_table("transcription_review_events")
    op.drop_table("transcription_reviews")
