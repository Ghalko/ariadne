from __future__ import annotations

from spinner.models import WorkspaceRecord

DEFAULT_WORKSPACES = {
    "spinner": WorkspaceRecord(
        name="spinner",
        path=".",
        branch="main",
        commit_sha="dev-sha",
        include_globs=["spinner/**/*.py", "docs/**/*.md", "config/**/*.toml", "tests/**/*.py"],
        exclude_globs=[".venv/**", "__pycache__/**"],
    )
}


def list_workspaces() -> list[WorkspaceRecord]:
    return list(DEFAULT_WORKSPACES.values())


def get_workspace(name: str) -> WorkspaceRecord:
    return DEFAULT_WORKSPACES[name]
