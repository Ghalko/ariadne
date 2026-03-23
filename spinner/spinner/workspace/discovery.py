from __future__ import annotations

from pathlib import Path

from spinner.workspace.registry import get_workspace


def discover_workspace_files(name: str) -> list[str]:
    workspace = get_workspace(name)
    root = Path(workspace.path)
    return sorted(str(path.relative_to(root)) for path in root.rglob("*.py"))
