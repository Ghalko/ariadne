from __future__ import annotations

from spinner.indexing.indexer import index_workspace
from spinner.models import RetrievalCandidate
from spinner.providers.embeddings import resolve_embedding_provider


SEMANTIC_HINTS = {
    "fallback": ["providers/embeddings.py", "providers/openai.py", "agent/runtime.py"],
    "rollback": ["patching/rollback.py", "patching/apply.py", "sessions/store.py"],
    "token": ["context/token_budget.py", "context/packer.py"],
}


def semantic_candidates(workspace: str, query: str) -> list[RetrievalCandidate]:
    provider = resolve_embedding_provider()
    lowered = query.lower()
    results: list[RetrievalCandidate] = []
    indexed_paths = {item["path"]: item["summary"] for item in index_workspace(workspace)}

    for token, paths in SEMANTIC_HINTS.items():
        if token not in lowered:
            continue
        for path in paths:
            results.append(
                RetrievalCandidate(
                    node_id=f"{path}:{provider['model']}",
                    node_type="file",
                    path=path,
                    score=7.5,
                    reason=f"semantic hint via {provider['model']}",
                    summary=indexed_paths.get(path, path),
                )
            )
    return results
