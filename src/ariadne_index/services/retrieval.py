from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from ariadne_index.models.entities import Embedding, FileRecord, Memory, Repo, RetrievalLog, SymbolRecord
from ariadne_index.models.enums import EdgeType, MemoryStatus
from ariadne_index.services.context_packing import ContextPacker
from ariadne_index.services.embeddings import DeterministicEmbeddingProvider, cosine_similarity
from ariadne_index.services.graph import GraphService
from ariadne_index.services.lexical import LexicalSearchService


MODE_WEIGHTS = {
    "understand": {"lexical": 1.0, "graph": 0.7, "semantic": 0.8, "memory": 0.7},
    "refactor": {"lexical": 0.8, "graph": 1.0, "semantic": 0.7, "memory": 0.9},
    "bugfix": {"lexical": 1.0, "graph": 0.8, "semantic": 0.8, "memory": 0.8},
    "testgen": {"lexical": 0.7, "graph": 1.0, "semantic": 0.6, "memory": 0.3},
    "docs": {"lexical": 0.8, "graph": 0.4, "semantic": 0.8, "memory": 0.9},
    "architecture": {"lexical": 0.7, "graph": 0.9, "semantic": 0.8, "memory": 1.0},
}


class RetrievalService:
    def __init__(self, session: Session, embedder: DeterministicEmbeddingProvider) -> None:
        self.session = session
        self.embedder = embedder
        self.lexical = LexicalSearchService(session)
        self.graph = GraphService(session)
        self.packer = ContextPacker(session)

    def retrieve(
        self,
        *,
        query: str,
        mode: str,
        repo: Repo | None,
        limit: int = 12,
        include_code: bool = True,
    ) -> dict:
        repo_id = repo.id if repo else None
        weights = MODE_WEIGHTS.get(mode, MODE_WEIGHTS["understand"])
        reasons: dict[str, str] = {}
        scores: dict[str, float] = defaultdict(float)

        lexical_results = self.lexical.search(query, repo_id=repo_id, limit=limit)
        files = list(lexical_results["files"])
        symbols = list(lexical_results["symbols"])
        memories = [memory for memory in lexical_results["memories"] if memory.status == MemoryStatus.active]

        for file in files:
            scores[f"file:{file.id}"] += 10 * weights["lexical"]
            reasons[f"file:{file.id}"] = "lexical match on path or summary"
        for symbol in symbols:
            scores[f"symbol:{symbol.id}"] += 12 * weights["lexical"]
            reasons[f"symbol:{symbol.id}"] = "lexical match on symbol metadata"
        for memory in memories:
            scores[f"memory:{memory.id}"] += 8 * weights["memory"]
            reasons[f"memory:{memory.id}"] = "memory text matched query"

        for symbol in symbols[: min(4, len(symbols))]:
            for neighbor in self.graph.traverse(
                start_kind="symbol",
                start_id=symbol.id,
                max_hops=2 if mode == "refactor" else 1,
                edge_types=[EdgeType.file_contains_symbol, EdgeType.test_covers_symbol, EdgeType.applies_to],
                limit=limit,
            ):
                key = f"{neighbor['node_kind']}:{neighbor['node_id']}"
                scores[key] += max(1.0, 6 - neighbor["hops"]) * weights["graph"]
                reasons[key] = f"graph expansion via {' > '.join(neighbor['path'])}"

        query_vector = self.embedder.embed(query)
        candidate_embeddings = self._candidate_embeddings(repo_id=repo_id, limit=limit * 8)
        for embedding in candidate_embeddings:
            similarity = cosine_similarity(query_vector, embedding.vector)
            if similarity <= 0:
                continue
            key = f"{embedding.node_kind}:{embedding.node_id}"
            scores[key] += similarity * 10 * weights["semantic"]
            reasons.setdefault(key, "semantic similarity to query")

        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)[: limit * 2]
        selected_files = self._load_entities(FileRecord, ordered, prefix="file")
        selected_symbols = self._load_entities(SymbolRecord, ordered, prefix="symbol")
        selected_memories = self._load_entities(Memory, ordered, prefix="memory")

        packed = self.packer.pack(
            repo=repo,
            files=selected_files[:limit],
            symbols=selected_symbols[:limit],
            memories=selected_memories[:limit],
            reasons=reasons,
            include_code=include_code,
        )
        self._log_retrieval(repo_id=repo_id, query=query, mode=mode, ordered=ordered, packed=packed)
        return {
            "mode": mode,
            "scores": [{"node": key, "score": score} for key, score in ordered[:limit]],
            "context": packed,
        }

    def _candidate_embeddings(self, repo_id: int | None, limit: int) -> list[Embedding]:
        query = self.session.query(Embedding)
        if repo_id is not None:
            query = query.filter(Embedding.repo_id == repo_id)
        return list(query.limit(limit))

    def _load_entities(self, model, ordered: list[tuple[str, float]], prefix: str):
        ids = [int(key.split(":")[1]) for key, _ in ordered if key.startswith(f"{prefix}:")]
        if not ids:
            return []
        items = self.session.query(model).filter(model.id.in_(ids)).all()
        items_by_id = {item.id: item for item in items}
        return [items_by_id[item_id] for item_id in ids if item_id in items_by_id]

    def _log_retrieval(
        self,
        *,
        repo_id: int | None,
        query: str,
        mode: str,
        ordered: list[tuple[str, float]],
        packed: dict,
    ) -> None:
        log = RetrievalLog(
            repo_id=repo_id,
            query_text=query,
            mode=mode,
            retrieved_node_ids=[
                {"node": key, "rank": index + 1}
                for index, (key, _) in enumerate(ordered[:25])
            ],
            scores=[{"node": key, "score": score} for key, score in ordered[:25]],
            packed_context=packed,
        )
        self.session.add(log)
        self.session.flush()
