"""Add retrieval diagnostics storage."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_retrieval_diagnostics"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "retrieval_logs",
        sa.Column("diagnostics_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("retrieval_logs", "diagnostics_json")
