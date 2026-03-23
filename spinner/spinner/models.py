from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class TaskMode(str, Enum):
    understand = "understand"
    refactor = "refactor"
    bugfix = "bugfix"
    docs = "docs"


@dataclass(slots=True)
class WorkspaceRecord:
    name: str
    path: str
    branch: str = "main"
    commit_sha: str = "unknown"
    include_globs: list[str] = field(default_factory=list)
    exclude_globs: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RetrievalCandidate:
    node_id: str
    node_type: str
    path: str
    score: float
    reason: str
    summary: str = ""


@dataclass(slots=True)
class ContextBundle:
    mode: TaskMode
    summaries: list[str] = field(default_factory=list)
    snippets: list[str] = field(default_factory=list)
    memories: list[str] = field(default_factory=list)
    estimated_tokens: int = 0


@dataclass(slots=True)
class TaskRequest:
    task_id: str
    query: str
    mode: TaskMode
    workspace: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class PatchPlan:
    task_id: str
    target_files: list[str]
    summary: str
    rollback_hint: str


@dataclass(slots=True)
class RunResult:
    task_id: str
    status: str
    message: str
    changed_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
