from __future__ import annotations

from spinner.indexing.graph_builder import build_graph_hints
from spinner.models import RetrievalCandidate


def graph_expand(candidates: list[RetrievalCandidate]) -> list[RetrievalCandidate]:
    expanded: list[RetrievalCandidate] = []
    for candidate in candidates:
        for path in build_graph_hints(candidate.path):
            expanded.append(
                RetrievalCandidate(
                    node_id=f"graph:{path}",
                    node_type="file",
                    path=path,
                    score=5.0,
                    reason=f"graph expansion from {candidate.path}",
                    summary="graph-related file",
                )
            )
    return expanded
