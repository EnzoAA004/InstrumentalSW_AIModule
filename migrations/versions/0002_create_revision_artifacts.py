"""create revision_artifact_bundles and revision_artifacts

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "revision_artifact_bundles",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("job_id", "revision_number"),
    )
    op.create_table(
        "revision_artifacts",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("artifact_id", sa.String(length=64), nullable=False),
        sa.Column("artifact_type", sa.String(length=16), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("media_type", sa.String(), nullable=False),
        sa.Column("extension", sa.String(length=16), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("job_id", "revision_number", "artifact_id"),
        sa.ForeignKeyConstraint(
            ["job_id", "revision_number"],
            ["revision_artifact_bundles.job_id", "revision_artifact_bundles.revision_number"],
        ),
    )


def downgrade() -> None:
    op.drop_table("revision_artifacts")
    op.drop_table("revision_artifact_bundles")
