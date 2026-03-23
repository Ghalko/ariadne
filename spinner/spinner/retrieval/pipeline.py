from __future__ import annotations

from spinner.models import RetrievalCandidate, TaskMode
from spinner.retrieval.graph import graph_expand
from spinner.retrieval.lexical import lexical_candidates
from spinner.retrieval.ranking import rank_candidates
from spinner.retrieval.semantic import semantic_candidates
from spinner.telemetry.events import record_retrieval_event


class RetrievalPipeline:
    def retrieve(self, *, workspace: str, query: str, mode: TaskMode) -> list[RetrievalCandidate]:
        lexical = lexical_candidates(workspace, query)
        semantic = semantic_candidates(workspace, query)
        graph = graph_expand(lexical)
        ranked = rank_candidates([*lexical, *semantic, *graph], limit=10 if mode == TaskMode.refactor else 6)
        record_retrieval_event(query=query, mode=mode.value, count=len(ranked))
        return ranked
