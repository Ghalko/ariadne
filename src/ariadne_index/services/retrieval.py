from __future__ import annotations

from collections import defaultdict
import re

from sqlalchemy.orm import Session

from ariadne_index.models.entities import Embedding, FileRecord, Memory, Repo, RetrievalLog, SymbolRecord
from ariadne_index.models.enums import EdgeType, MemoryStatus
from ariadne_index.services.context_packing import ContextPacker
from ariadne_index.services.embeddings import EmbeddingProvider, cosine_similarity
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
    def __init__(self, session: Session, embedder: EmbeddingProvider) -> None:
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
            scores[f"symbol:{symbol.id}"] += 14 * weights["lexical"]
            reasons[f"symbol:{symbol.id}"] = "lexical match on symbol metadata"
            scores[f"file:{symbol.file_id}"] += 7 * weights["graph"]
            reasons.setdefault(f"file:{symbol.file_id}", "file contains matched symbol")
        for memory in memories:
            scores[f"memory:{memory.id}"] += 8 * weights["memory"]
            reasons[f"memory:{memory.id}"] = "memory text matched query"

        self._expand_support_artifacts(
            repo_id=repo_id,
            query=query,
            mode=mode,
            files=files,
            symbols=symbols,
            scores=scores,
            reasons=reasons,
            weight=weights,
        )

        for symbol in symbols[: min(4, len(symbols))]:
            for neighbor in self.graph.traverse(
                start_kind="symbol",
                start_id=symbol.id,
                max_hops=2 if mode == "refactor" else 1,
                edge_types=[
                    EdgeType.file_contains_symbol,
                    EdgeType.test_covers_symbol,
                    EdgeType.doc_describes_symbol,
                    EdgeType.config_affects_file,
                    EdgeType.applies_to,
                ],
                limit=limit,
            ):
                key = f"{neighbor['node_kind']}:{neighbor['node_id']}"
                scores[key] += self._graph_edge_score(
                    edge_path=neighbor["path"],
                    mode=mode,
                    query=query,
                    hops=neighbor["hops"],
                    graph_weight=weights["graph"],
                )
                reasons[key] = f"graph expansion via {' > '.join(neighbor['path'])}"
                self._promote_symbol_owner_file(
                    key=key,
                    scores=scores,
                    reasons=reasons,
                    graph_weight=weights["graph"],
                    reason="owner file promoted from graph symbol expansion",
                )

        for file in files[: min(3, len(files))]:
            for neighbor in self.graph.traverse(
                start_kind="file",
                start_id=file.id,
                max_hops=2 if self._is_support_file(file) else 1,
                edge_types=[
                    EdgeType.file_imports_file,
                    EdgeType.file_contains_symbol,
                    EdgeType.test_covers_symbol,
                    EdgeType.doc_describes_symbol,
                    EdgeType.applies_to,
                    EdgeType.config_affects_file,
                ],
                limit=limit,
            ):
                key = f"{neighbor['node_kind']}:{neighbor['node_id']}"
                scores[key] += self._graph_edge_score(
                    edge_path=neighbor["path"],
                    mode=mode,
                    query=query,
                    hops=neighbor["hops"],
                    graph_weight=weights["graph"],
                )
                reasons.setdefault(key, f"graph expansion via {' > '.join(neighbor['path'])}")
                self._promote_symbol_owner_file(
                    key=key,
                    scores=scores,
                    reasons=reasons,
                    graph_weight=weights["graph"],
                    reason="owner file promoted from support artifact graph expansion",
                )

        for memory in memories[: min(3, len(memories))]:
            for neighbor in self.graph.traverse(
                start_kind="memory",
                start_id=memory.id,
                max_hops=2,
                edge_types=[
                    EdgeType.applies_to,
                    EdgeType.constrains,
                    EdgeType.warns_about,
                    EdgeType.implemented_by,
                    EdgeType.file_contains_symbol,
                ],
                limit=limit,
            ):
                key = f"{neighbor['node_kind']}:{neighbor['node_id']}"
                scores[key] += self._graph_edge_score(
                    edge_path=neighbor["path"],
                    mode=mode,
                    query=query,
                    hops=neighbor["hops"],
                    graph_weight=weights["graph"],
                )
                reasons.setdefault(key, f"memory graph expansion via {' > '.join(neighbor['path'])}")
                self._promote_symbol_owner_file(
                    key=key,
                    scores=scores,
                    reasons=reasons,
                    graph_weight=weights["graph"],
                    reason="owner file promoted from memory link",
                )

        query_vector = self.embedder.embed(query)
        candidate_embeddings = self._candidate_embeddings(repo_id=repo_id, limit=limit * 8)
        for embedding in candidate_embeddings:
            similarity = cosine_similarity(query_vector, embedding.vector)
            if similarity <= 0:
                continue
            key = f"{embedding.node_kind}:{embedding.node_id}"
            scores[key] += similarity * 10 * weights["semantic"]
            reasons.setdefault(key, "semantic similarity to query")

        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)[: limit * 4]
        selected = self._select_ranked_by_type(ordered, mode=mode, limit=limit)
        selected_files = self._load_entities(FileRecord, selected, prefix="file")
        selected_symbols = self._load_entities(SymbolRecord, selected, prefix="symbol")
        selected_memories = self._load_entities(Memory, selected, prefix="memory")

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

    def _select_ranked_by_type(self, ordered: list[tuple[str, float]], *, mode: str, limit: int) -> list[tuple[str, float]]:
        memory_quota = 3 if mode in {"architecture", "docs", "refactor"} else 2
        quotas = {
            "file": max(limit, 8),
            "symbol": max(4, min(limit, 6)),
            "memory": memory_quota,
        }
        counts = defaultdict(int)
        selected: list[tuple[str, float]] = []

        for key, score in ordered:
            node_kind = key.split(":", 1)[0]
            quota = quotas.get(node_kind)
            if quota is None or counts[node_kind] >= quota:
                continue
            selected.append((key, score))
            counts[node_kind] += 1

            if all(counts[node_kind] >= quota for node_kind, quota in quotas.items() if any(item[0].startswith(f"{node_kind}:") for item in ordered)):
                break

        return selected

    def _candidate_embeddings(self, repo_id: int | None, limit: int) -> list[Embedding]:
        query = self.session.query(Embedding)
        if repo_id is not None:
            query = query.filter(Embedding.repo_id == repo_id)
        return list(query.limit(limit))

    def _promote_symbol_owner_file(
        self,
        *,
        key: str,
        scores: dict[str, float],
        reasons: dict[str, str],
        graph_weight: float,
        reason: str,
    ) -> None:
        if not key.startswith("symbol:"):
            return
        symbol_id = int(key.split(":", 1)[1])
        symbol = self.session.get(SymbolRecord, symbol_id)
        if symbol is None:
            return
        file_key = f"file:{symbol.file_id}"
        scores[file_key] += 6.0 * graph_weight
        reasons.setdefault(file_key, reason)

    def _is_support_file(self, file: FileRecord) -> bool:
        return self._is_test(file) or self._is_doc(file) or self._is_config(file)

    def _is_test(self, file: FileRecord) -> bool:
        return "test" in file.tags or file.path.startswith("tests/") or "/test" in file.path

    def _is_doc(self, file: FileRecord) -> bool:
        return file.path.startswith("docs/") or file.language.value == "markdown"

    def _is_config(self, file: FileRecord) -> bool:
        return file.path.startswith("config/") or file.language.value in {"toml", "yaml", "json"}

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

    def _expand_support_artifacts(
        self,
        *,
        repo_id: int | None,
        query: str,
        mode: str,
        files: list[FileRecord],
        symbols: list[SymbolRecord],
        scores: dict[str, float],
        reasons: dict[str, str],
        weight: dict[str, float],
    ) -> None:
        if repo_id is None:
            return

        terms = self._terms(query)
        doc_focused = any(term in query.lower() for term in ("doc", "docs", "runbook", "decision", "architecture", "adr"))
        symbol_terms = {
            piece.lower()
            for symbol in symbols
            for piece in re.split(r"[_\W]+", symbol.name)
            if len(piece) >= 3
        }
        primary_files = {file.id: file for file in files}
        for symbol in symbols:
            file_record = self.session.get(FileRecord, symbol.file_id)
            if file_record is not None:
                primary_files[file_record.id] = file_record

        candidate_terms = {*terms, *symbol_terms}
        primary_modules = {file.path.removesuffix(".py").replace("/", ".") for file in primary_files.values()}
        all_files = list(self.session.query(FileRecord).filter(FileRecord.repo_id == repo_id))

        for file in all_files:
            if file.id in primary_files:
                continue
            path_text = f"{file.path} {file.summary or ''}".lower()
            overlap = any(term in path_text for term in candidate_terms)
            imports_primary = any(imported in primary_modules for imported in file.imports)
            is_test = "test" in file.tags or file.path.startswith("tests/") or "/test" in file.path
            is_doc = file.path.startswith("docs/") or file.language.value == "markdown"
            is_config = file.path.startswith("config/") or file.language.value in {"toml", "yaml", "json"}

            if is_test and (imports_primary or overlap) and mode in {"understand", "refactor", "bugfix", "testgen"}:
                scores[f"file:{file.id}"] += 12.0 * weight["graph"]
                reasons.setdefault(f"file:{file.id}", "related test expansion")
            elif is_doc and overlap and doc_focused:
                scores[f"file:{file.id}"] += 5.0 * weight["graph"]
                reasons.setdefault(f"file:{file.id}", "related documentation expansion")
            elif is_config and overlap:
                scores[f"file:{file.id}"] += 5.0 * weight["graph"]
                reasons.setdefault(f"file:{file.id}", "related config expansion")

        active_memories = (
            self.session.query(Memory)
            .filter(Memory.status == MemoryStatus.active)
            .filter((Memory.repo_id == repo_id) | (Memory.repo_id.is_(None)))
            .all()
        )
        for memory in active_memories:
            text = f"{memory.title} {memory.summary or ''} {memory.content}".lower()
            overlap = any(term in text for term in candidate_terms)
            type_signal = any(
                phrase in query.lower()
                for phrase in ("decision", "runbook", "incident", "architecture", "prior")
            )
            if overlap or (type_signal and any(term in text for term in terms)):
                scores[f"memory:{memory.id}"] += (6.0 if type_signal else 4.0) * weight["memory"]
                reasons.setdefault(f"memory:{memory.id}", "memory expansion from related task context")

    def _terms(self, query: str) -> list[str]:
        return [term for term in re.split(r"\W+", query.lower()) if len(term) >= 3]

    def _graph_edge_score(
        self,
        *,
        edge_path: list[str],
        mode: str,
        query: str,
        hops: int,
        graph_weight: float,
    ) -> float:
        edge_type = edge_path[-1] if edge_path else ""
        query_lower = query.lower()

        if edge_type == EdgeType.test_covers_symbol.value:
            base = 8.0 if mode in {"refactor", "bugfix", "testgen"} else 6.0
        elif edge_type == EdgeType.file_contains_symbol.value:
            base = 5.5
        elif edge_type == EdgeType.file_imports_file.value:
            base = 5.0
        elif edge_type == EdgeType.applies_to.value:
            base = 5.0
        elif edge_type == EdgeType.doc_describes_symbol.value:
            base = 5.0 if mode in {"docs", "architecture"} or any(
                term in query_lower for term in ("doc", "docs", "runbook", "decision", "architecture", "adr")
            ) else 2.0
        else:
            base = 3.0

        return max(1.0, base - (hops - 1)) * graph_weight
