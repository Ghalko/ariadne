from __future__ import annotations

from spinner.indexing.indexer import index_workspace
from spinner.models import RetrievalCandidate


def lexical_candidates(workspace: str, query: str) -> list[RetrievalCandidate]:
    lowered = query.lower()
    results: list[RetrievalCandidate] = []
    for item in index_workspace(workspace):
        haystack = f"{item['path']} {item['summary']}".lower()
        if any(term in haystack for term in lowered.split()):
            results.append(
                RetrievalCandidate(
                    node_id=item["path"],
                    node_type="file",
                    path=item["path"],
                    score=10.0,
                    reason="lexical match",
                    summary=item["summary"],
                )
            )
    return results
