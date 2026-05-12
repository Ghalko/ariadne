"""Add UUID identity columns."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_uuid_identity_columns"
down_revision = "0002_retrieval_diagnostics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in ("repos", "files", "symbols", "memories", "edges", "embeddings", "retrieval_logs"):
        op.add_column(table_name, sa.Column("uuid", sa.String(length=36), nullable=True))
        op.create_index(f"ix_{table_name}_uuid", table_name, ["uuid"], unique=table_name != "edges")

    op.add_column("edges", sa.Column("from_node_uuid", sa.String(length=36), nullable=True))
    op.add_column("edges", sa.Column("to_node_uuid", sa.String(length=36), nullable=True))
    op.create_index("ix_edges_from_node_uuid", "edges", ["from_node_uuid"])
    op.create_index("ix_edges_to_node_uuid", "edges", ["to_node_uuid"])

    op.add_column("embeddings", sa.Column("node_uuid", sa.String(length=36), nullable=True))
    op.create_index("ix_embeddings_node_uuid", "embeddings", ["node_uuid"])


def downgrade() -> None:
    op.drop_index("ix_embeddings_node_uuid", table_name="embeddings")
    op.drop_column("embeddings", "node_uuid")

    op.drop_index("ix_edges_to_node_uuid", table_name="edges")
    op.drop_index("ix_edges_from_node_uuid", table_name="edges")
    op.drop_column("edges", "to_node_uuid")
    op.drop_column("edges", "from_node_uuid")

    for table_name in reversed(("repos", "files", "symbols", "memories", "edges", "embeddings", "retrieval_logs")):
        op.drop_index(f"ix_{table_name}_uuid", table_name=table_name)
        op.drop_column(table_name, "uuid")
