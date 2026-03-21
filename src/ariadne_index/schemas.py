from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ariadne_index.models.enums import EdgeType, MemorySource, MemoryStatus, MemoryType


class RepoCreate(BaseModel):
    name: str
    local_path: str
    default_branch: str | None = None
    active_branch: str | None = None
    current_commit_sha: str | None = None
    include_globs: list[str] = Field(default_factory=list)
    exclude_globs: list[str] = Field(default_factory=list)


class MemoryCreate(BaseModel):
    repo_id: int | None = None
    title: str
    content: str
    summary: str | None = None
    memory_type: MemoryType
    status: MemoryStatus = MemoryStatus.active
    source: MemorySource = MemorySource.manual
    confidence: float = 1.0
    author: str | None = None
    owner: str | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class MemoryLinkCreate(BaseModel):
    from_memory_id: int
    to_node_kind: str
    to_node_id: int
    edge_type: EdgeType = EdgeType.applies_to
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class SearchQuery(BaseModel):
    query: str
    repo_name: str | None = None
    limit: int = 10


class RetrieveQuery(BaseModel):
    query: str
    mode: str = "understand"
    repo_name: str | None = None
    limit: int = 12
    include_code: bool = True


class GraphQuery(BaseModel):
    node_kind: str
    node_id: int
    edge_types: list[EdgeType] = Field(default_factory=list)
    max_hops: int = 1
    limit: int = 20
