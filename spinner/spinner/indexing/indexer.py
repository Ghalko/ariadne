from __future__ import annotations

from spinner.indexing.discovery import discover_index_inputs
from spinner.indexing.graph_builder import build_graph_hints
from spinner.indexing.summaries import summarize_file


def index_workspace(workspace: str) -> list[dict]:
    indexed: list[dict] = []
    for path in discover_index_inputs(workspace):
        indexed.append(
            {
                "path": path,
                "summary": summarize_file(path),
                "graph_hints": build_graph_hints(path),
            }
        )
    return indexed
