from __future__ import annotations

from spinner.workspace.discovery import discover_workspace_files


def discover_index_inputs(workspace: str) -> list[str]:
    return [path for path in discover_workspace_files(workspace) if path.endswith(".py")]
