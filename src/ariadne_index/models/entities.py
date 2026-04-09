from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ariadne_index.config import get_settings
from ariadne_index.models.base import Base
from ariadne_index.models.enums import EdgeType, FileLanguage, MemorySource, MemoryStatus, MemoryType
from ariadne_index.models.types import EmbeddingType

settings = get_settings()


class Repo(Base):
    __tablename__ = "repos"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    local_path: Mapped[str] = mapped_column(Text, unique=True)
    default_branch: Mapped[str | None] = mapped_column(String(255))
    active_branch: Mapped[str | None] = mapped_column(String(255))
    current_commit_sha: Mapped[str | None] = mapped_column(String(64), index=True)
    include_globs: Mapped[list[str]] = mapped_column(JSON, default=list)
    exclude_globs: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    files: Mapped[list["FileRecord"]] = relationship(back_populates="repo", cascade="all, delete-orphan")


class FileRecord(Base):
    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("repo_id", "path", name="uq_files_repo_path"),
        Index("ix_files_repo_language", "repo_id", "language"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(Text, index=True)
    language: Mapped[FileLanguage] = mapped_column(Enum(FileLanguage), default=FileLanguage.unknown)
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    commit_sha: Mapped[str | None] = mapped_column(String(64), index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    imports: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    repo: Mapped[Repo] = relationship(back_populates="files")
    symbols: Mapped[list["SymbolRecord"]] = relationship(back_populates="file", cascade="all, delete-orphan")


class SymbolRecord(Base):
    __tablename__ = "symbols"
    __table_args__ = (
        UniqueConstraint("file_id", "name", "line_start", "line_end", name="uq_symbol_file_name_range"),
        Index("ix_symbols_name_type", "name", "symbol_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), index=True)
    parent_symbol_id: Mapped[int | None] = mapped_column(ForeignKey("symbols.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(255), index=True)
    qualified_name: Mapped[str | None] = mapped_column(Text, index=True)
    symbol_type: Mapped[str] = mapped_column(String(64), index=True)
    language: Mapped[FileLanguage] = mapped_column(Enum(FileLanguage), default=FileLanguage.unknown)
    line_start: Mapped[int] = mapped_column(Integer)
    line_end: Mapped[int] = mapped_column(Integer)
    signature: Mapped[str | None] = mapped_column(Text)
    docstring: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    file: Mapped[FileRecord] = relationship(back_populates="symbols")


class Memory(Base):
    __tablename__ = "memories"
    __table_args__ = (Index("ix_memory_type_status", "memory_type", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int | None] = mapped_column(ForeignKey("repos.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    content: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    memory_type: Mapped[MemoryType] = mapped_column(Enum(MemoryType), index=True)
    status: Mapped[MemoryStatus] = mapped_column(Enum(MemoryStatus), default=MemoryStatus.active)
    source: Mapped[MemorySource] = mapped_column(Enum(MemorySource), default=MemorySource.manual)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    author: Mapped[str | None] = mapped_column(String(255))
    owner: Mapped[str | None] = mapped_column(String(255))
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Edge(Base):
    __tablename__ = "edges"
    __table_args__ = (
        Index("ix_edges_from_type", "from_node_kind", "from_node_id", "edge_type"),
        Index("ix_edges_to_type", "to_node_kind", "to_node_id", "edge_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int | None] = mapped_column(ForeignKey("repos.id", ondelete="CASCADE"), index=True)
    from_node_kind: Mapped[str] = mapped_column(String(64))
    from_node_id: Mapped[int] = mapped_column(Integer)
    to_node_kind: Mapped[str] = mapped_column(String(64))
    to_node_id: Mapped[int] = mapped_column(Integer)
    edge_type: Mapped[EdgeType] = mapped_column(Enum(EdgeType), index=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Embedding(Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        UniqueConstraint("node_kind", "node_id", "embedding_role", name="uq_embedding_node_role"),
        Index("ix_embeddings_node_kind", "node_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int | None] = mapped_column(ForeignKey("repos.id", ondelete="CASCADE"), index=True)
    node_kind: Mapped[str] = mapped_column(String(64))
    node_id: Mapped[int] = mapped_column(Integer)
    embedding_role: Mapped[str] = mapped_column(String(64), default="summary")
    model_name: Mapped[str] = mapped_column(String(255), default=settings.embedding_model)
    dimensions: Mapped[int] = mapped_column(Integer, default=settings.embedding_dimensions)
    vector: Mapped[list[float]] = mapped_column(EmbeddingType(settings.embedding_dimensions))
    content_preview: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RetrievalLog(Base):
    __tablename__ = "retrieval_logs"
    __table_args__ = (Index("ix_retrieval_logs_mode_created", "mode", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int | None] = mapped_column(ForeignKey("repos.id", ondelete="SET NULL"), index=True)
    query_text: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(64), index=True)
    retrieved_node_ids: Mapped[list[dict]] = mapped_column(JSON, default=list)
    scores: Mapped[list[dict]] = mapped_column(JSON, default=list)
    diagnostics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    packed_context: Mapped[dict] = mapped_column(JSON, default=dict)
    outcome: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
