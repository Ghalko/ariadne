from __future__ import annotations

from spinner.workspace.registry import get_workspace


def workspace_status(name: str) -> dict:
    workspace = get_workspace(name)
    return {
        "name": workspace.name,
        "path": workspace.path,
        "branch": workspace.branch,
        "commit_sha": workspace.commit_sha,
    }
