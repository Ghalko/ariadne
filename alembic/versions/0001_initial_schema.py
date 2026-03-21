"""Initial Ariadne schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repos",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("local_path", sa.Text(), nullable=False, unique=True),
        sa.Column("default_branch", sa.String(length=255)),
        sa.Column("active_branch", sa.String(length=255)),
        sa.Column("current_commit_sha", sa.String(length=64)),
        sa.Column("include_globs", sa.JSON(), nullable=False),
        sa.Column("exclude_globs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_repos_name", "repos", ["name"])
    op.create_index("ix_repos_current_commit_sha", "repos", ["current_commit_sha"])

    op.create_table(
        "files",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("repo_id", sa.Integer(), sa.ForeignKey("repos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=32), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("commit_sha", sa.String(length=64)),
        sa.Column("summary", sa.Text()),
        sa.Column("imports", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("repo_id", "path", name="uq_files_repo_path"),
    )
    op.create_index("ix_files_repo_id", "files", ["repo_id"])
    op.create_index("ix_files_path", "files", ["path"])
    op.create_index("ix_files_checksum", "files", ["checksum"])
    op.create_index("ix_files_commit_sha", "files", ["commit_sha"])
    op.create_index("ix_files_repo_language", "files", ["repo_id", "language"])

    op.create_table(
        "symbols",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("repo_id", sa.Integer(), sa.ForeignKey("repos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_symbol_id", sa.Integer(), sa.ForeignKey("symbols.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("qualified_name", sa.Text()),
        sa.Column("symbol_type", sa.String(length=64), nullable=False),
        sa.Column("language", sa.String(length=32), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.Column("signature", sa.Text()),
        sa.Column("docstring", sa.Text()),
        sa.Column("summary", sa.Text()),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("file_id", "name", "line_start", "line_end", name="uq_symbol_file_name_range"),
    )
    op.create_index("ix_symbols_repo_id", "symbols", ["repo_id"])
    op.create_index("ix_symbols_file_id", "symbols", ["file_id"])
    op.create_index("ix_symbols_name", "symbols", ["name"])
    op.create_index("ix_symbols_qualified_name", "symbols", ["qualified_name"])
    op.create_index("ix_symbols_symbol_type", "symbols", ["symbol_type"])
    op.create_index("ix_symbols_name_type", "symbols", ["name", "symbol_type"])

    op.create_table(
        "memories",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("repo_id", sa.Integer(), sa.ForeignKey("repos.id", ondelete="CASCADE")),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("memory_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("author", sa.String(length=255)),
        sa.Column("owner", sa.String(length=255)),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_memories_repo_id", "memories", ["repo_id"])
    op.create_index("ix_memories_title", "memories", ["title"])
    op.create_index("ix_memory_type_status", "memories", ["memory_type", "status"])

    op.create_table(
        "edges",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("repo_id", sa.Integer(), sa.ForeignKey("repos.id", ondelete="CASCADE")),
        sa.Column("from_node_kind", sa.String(length=64), nullable=False),
        sa.Column("from_node_id", sa.Integer(), nullable=False),
        sa.Column("to_node_kind", sa.String(length=64), nullable=False),
        sa.Column("to_node_id", sa.Integer(), nullable=False),
        sa.Column("edge_type", sa.String(length=64), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_edges_repo_id", "edges", ["repo_id"])
    op.create_index("ix_edges_edge_type", "edges", ["edge_type"])
    op.create_index("ix_edges_from_type", "edges", ["from_node_kind", "from_node_id", "edge_type"])
    op.create_index("ix_edges_to_type", "edges", ["to_node_kind", "to_node_id", "edge_type"])

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE TABLE embeddings ("
               "id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, "
               "repo_id INTEGER REFERENCES repos(id) ON DELETE CASCADE, "
               "node_kind VARCHAR(64) NOT NULL, "
               "node_id INTEGER NOT NULL, "
               "embedding_role VARCHAR(64) NOT NULL, "
               "model_name VARCHAR(255) NOT NULL, "
               "dimensions INTEGER NOT NULL, "
               "vector vector(24) NOT NULL, "
               "content_preview TEXT, "
               "created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, "
               "CONSTRAINT uq_embedding_node_role UNIQUE (node_kind, node_id, embedding_role))")
    op.execute("CREATE INDEX ix_embeddings_repo_id ON embeddings (repo_id)")
    op.execute("CREATE INDEX ix_embeddings_node_kind ON embeddings (node_kind)")
    op.execute(
        "CREATE INDEX ix_embeddings_vector_hnsw "
        "ON embeddings USING hnsw (vector vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )

    op.create_table(
        "retrieval_logs",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("repo_id", sa.Integer(), sa.ForeignKey("repos.id", ondelete="SET NULL")),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(length=64), nullable=False),
        sa.Column("retrieved_node_ids", sa.JSON(), nullable=False),
        sa.Column("scores", sa.JSON(), nullable=False),
        sa.Column("packed_context", sa.JSON(), nullable=False),
        sa.Column("outcome", sa.String(length=64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_retrieval_logs_repo_id", "retrieval_logs", ["repo_id"])
    op.create_index("ix_retrieval_logs_mode", "retrieval_logs", ["mode"])
    op.create_index("ix_retrieval_logs_mode_created", "retrieval_logs", ["mode", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_retrieval_logs_mode_created", table_name="retrieval_logs")
    op.drop_index("ix_retrieval_logs_mode", table_name="retrieval_logs")
    op.drop_index("ix_retrieval_logs_repo_id", table_name="retrieval_logs")
    op.drop_table("retrieval_logs")
    op.execute("DROP INDEX IF EXISTS ix_embeddings_vector_hnsw")
    op.execute("DROP TABLE IF EXISTS embeddings")
    op.drop_index("ix_edges_to_type", table_name="edges")
    op.drop_index("ix_edges_from_type", table_name="edges")
    op.drop_index("ix_edges_edge_type", table_name="edges")
    op.drop_index("ix_edges_repo_id", table_name="edges")
    op.drop_table("edges")
    op.drop_index("ix_memory_type_status", table_name="memories")
    op.drop_index("ix_memories_title", table_name="memories")
    op.drop_index("ix_memories_repo_id", table_name="memories")
    op.drop_table("memories")
    op.drop_index("ix_symbols_name_type", table_name="symbols")
    op.drop_index("ix_symbols_symbol_type", table_name="symbols")
    op.drop_index("ix_symbols_qualified_name", table_name="symbols")
    op.drop_index("ix_symbols_name", table_name="symbols")
    op.drop_index("ix_symbols_file_id", table_name="symbols")
    op.drop_index("ix_symbols_repo_id", table_name="symbols")
    op.drop_table("symbols")
    op.drop_index("ix_files_repo_language", table_name="files")
    op.drop_index("ix_files_commit_sha", table_name="files")
    op.drop_index("ix_files_checksum", table_name="files")
    op.drop_index("ix_files_path", table_name="files")
    op.drop_index("ix_files_repo_id", table_name="files")
    op.drop_table("files")
    op.execute("DROP INDEX IF EXISTS ix_repos_current_commit_sha")
    op.execute("DROP INDEX IF EXISTS ix_repos_name")
    op.execute("DROP TABLE IF EXISTS repos")
