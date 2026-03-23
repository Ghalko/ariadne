from __future__ import annotations

from spinner.models import RetrievalCandidate


def rank_candidates(candidates: list[RetrievalCandidate], limit: int = 8) -> list[RetrievalCandidate]:
    by_path: dict[str, RetrievalCandidate] = {}
    for candidate in candidates:
        existing = by_path.get(candidate.path)
        if existing is None or candidate.score > existing.score:
            by_path[candidate.path] = candidate
    return sorted(by_path.values(), key=lambda item: item.score, reverse=True)[:limit]
