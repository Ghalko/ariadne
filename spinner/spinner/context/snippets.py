from __future__ import annotations

from spinner.models import RetrievalCandidate


def pick_snippets(candidates: list[RetrievalCandidate], limit: int = 3) -> list[str]:
    return [f"{candidate.path}: {candidate.reason}" for candidate in candidates[:limit]]
