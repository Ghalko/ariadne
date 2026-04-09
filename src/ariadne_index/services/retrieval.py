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
        diagnostics = self._new_diagnostics()

        lexical_results = self.lexical.search(query, repo_id=repo_id, limit=limit)
        files = list(lexical_results["files"])
        symbols = list(lexical_results["symbols"])
        memories = [memory for memory in lexical_results["memories"] if memory.status == MemoryStatus.active]

        for file in files:
            scores[f"file:{file.id}"] += 10 * weights["lexical"]
            reasons[f"file:{file.id}"] = "lexical match on path or summary"
            self._record_stage_hit(diagnostics, "lexical", f"file:{file.id}")
        for symbol in symbols:
            scores[f"symbol:{symbol.id}"] += 14 * weights["lexical"]
            reasons[f"symbol:{symbol.id}"] = "lexical match on symbol metadata"
            scores[f"file:{symbol.file_id}"] += 7 * weights["graph"]
            reasons.setdefault(f"file:{symbol.file_id}", "file contains matched symbol")
            self._record_stage_hit(diagnostics, "lexical", f"symbol:{symbol.id}")
        for memory in memories:
            scores[f"memory:{memory.id}"] += 8 * weights["memory"]
            reasons[f"memory:{memory.id}"] = "memory text matched query"
            self._record_stage_hit(diagnostics, "lexical", f"memory:{memory.id}")

        self._expand_support_artifacts(
            repo_id=repo_id,
            query=query,
            mode=mode,
            files=files,
            symbols=symbols,
            scores=scores,
            reasons=reasons,
            weight=weights,
            diagnostics=diagnostics,
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
                    EdgeType.doc_describes_file,
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
                self._record_stage_hit(diagnostics, "graph", key)
                self._promote_symbol_owner_file(
                    key=key,
                    scores=scores,
                    reasons=reasons,
                    graph_weight=weights["graph"],
                    mode=mode,
                    source="symbol",
                    reason="owner file promoted from graph symbol expansion",
                    diagnostics=diagnostics,
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
                    EdgeType.doc_describes_file,
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
                self._record_stage_hit(diagnostics, "graph", key)
                self._promote_symbol_owner_file(
                    key=key,
                    scores=scores,
                    reasons=reasons,
                    graph_weight=weights["graph"],
                    mode=mode,
                    source="support",
                    reason="owner file promoted from support artifact graph expansion",
                    diagnostics=diagnostics,
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
                self._record_stage_hit(diagnostics, "graph", key)
                self._promote_symbol_owner_file(
                    key=key,
                    scores=scores,
                    reasons=reasons,
                    graph_weight=weights["graph"],
                    mode=mode,
                    source="memory",
                    reason="owner file promoted from memory link",
                    diagnostics=diagnostics,
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
            self._record_stage_hit(diagnostics, "semantic", key)

        self._rerank_support_files(
            query=query,
            mode=mode,
            scores=scores,
            reasons=reasons,
        )
        self._expand_symbols_from_ranked_files(
            query=query,
            mode=mode,
            scores=scores,
            reasons=reasons,
            diagnostics=diagnostics,
        )

        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)[: limit * 4]
        selected = self._select_ranked_by_type(ordered, query=query, mode=mode, limit=limit)
        selected_files = self._load_entities(FileRecord, selected, prefix="file")
        selected_symbols = self._load_entities(SymbolRecord, selected, prefix="symbol")
        selected_memories = self._load_entities(Memory, selected, prefix="memory")
        self._record_selected_entities(diagnostics, selected_files, selected_symbols, selected_memories)

        packed = self.packer.pack(
            repo=repo,
            mode=mode,
            query=query,
            files=selected_files[:limit],
            symbols=selected_symbols[:limit],
            memories=selected_memories[:limit],
            reasons=reasons,
            include_code=include_code,
        )
        self._record_packed_entities(diagnostics, packed)
        self._log_retrieval(repo_id=repo_id, query=query, mode=mode, ordered=ordered, packed=packed)
        return {
            "mode": mode,
            "scores": [{"node": key, "score": float(score)} for key, score in ordered[:limit]],
            "context": packed,
            "diagnostics": self._render_diagnostics(diagnostics, ordered=ordered, reasons=reasons),
        }

    def _select_ranked_by_type(
        self,
        ordered: list[tuple[str, float]],
        *,
        query: str,
        mode: str,
        limit: int,
    ) -> list[tuple[str, float]]:
        memory_quota = 3 if mode in {"architecture", "docs", "refactor"} else 2
        quotas = {
            "file": max(limit, 8),
            "symbol": max(4, min(limit, 6)),
            "memory": memory_quota,
        }
        counts = defaultdict(int)
        selected: list[tuple[str, float]] = []
        file_candidates = [(key, score) for key, score in ordered if key.startswith("file:")]
        file_keys = {key for key, _ in file_candidates}

        for key, score in self._select_files_by_mix(file_candidates, query=query, mode=mode, limit=quotas["file"]):
            selected.append((key, score))
            counts["file"] += 1

        for key, score in ordered:
            node_kind = key.split(":", 1)[0]
            quota = quotas.get(node_kind)
            if quota is None or counts[node_kind] >= quota:
                continue
            if node_kind == "file" and key in file_keys:
                continue
            selected.append((key, score))
            counts[node_kind] += 1

            if all(counts[node_kind] >= quota for node_kind, quota in quotas.items() if any(item[0].startswith(f"{node_kind}:") for item in ordered)):
                break

        return selected

    def _select_files_by_mix(
        self,
        file_candidates: list[tuple[str, float]],
        *,
        query: str,
        mode: str,
        limit: int,
    ) -> list[tuple[str, float]]:
        if not file_candidates:
            return []

        code_files: list[tuple[str, float]] = []
        tests: list[tuple[str, float]] = []
        docs: list[tuple[str, float]] = []
        configs: list[tuple[str, float]] = []

        for key, score in file_candidates:
            file_id = int(key.split(":", 1)[1])
            file = self.session.get(FileRecord, file_id)
            if file is None:
                continue
            if self._is_test(file):
                tests.append((key, score))
            elif self._is_doc(file):
                docs.append((key, score))
            elif self._is_config(file):
                configs.append((key, score))
            else:
                code_files.append((key, score))

        code_limit, test_limit, doc_limit, config_limit = self._file_selection_mix(mode=mode, query=query, limit=limit)
        selected = [
            *code_files[:code_limit],
            *tests[:test_limit],
            *docs[:doc_limit],
            *configs[:config_limit],
        ]

        seen = {key for key, _ in selected}
        for candidate in file_candidates:
            if len(selected) >= limit:
                break
            if candidate[0] in seen:
                continue
            seen.add(candidate[0])
            selected.append(candidate)
        return selected

    def _file_selection_mix(self, *, mode: str, query: str, limit: int) -> tuple[int, int, int, int]:
        if mode == "docs":
            base = [2, 1, 3, 2]
        elif mode == "architecture":
            base = [3, 0, 3, 1]
        elif mode in {"refactor", "bugfix", "testgen"}:
            base = [4, 2, 1, 1]
        else:
            base = [4, 1, 2, 1]

        lowered = query.lower()
        if self._is_doc_focused_query(lowered):
            base[2] = max(base[2], 3 if mode in {"docs", "architecture"} else 2)
            base[0] = max(2, base[0] - 1)
        if self._is_config_focused_query(lowered):
            base[3] = max(base[3], 2)
            if mode in {"understand", "docs", "architecture"}:
                base[2] = max(base[2], 2)
        if self._is_test_focused_query(lowered):
            base[1] = max(base[1], 2)

        total = sum(base)
        while total > limit:
            for index in (0, 1, 2, 3):
                minimum = 2 if index == 0 else 1 if base[index] > 0 else 0
                if base[index] > minimum:
                    base[index] -= 1
                    total -= 1
                    break
            else:
                break
        return tuple(base)

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
        mode: str,
        source: str,
        reason: str,
        diagnostics: dict[str, dict[str, set[int]]],
    ) -> None:
        if not key.startswith("symbol:"):
            return
        symbol_id = int(key.split(":", 1)[1])
        symbol = self.session.get(SymbolRecord, symbol_id)
        if symbol is None:
            return
        file_key = f"file:{symbol.file_id}"
        scores[file_key] += self._owner_file_promotion_weight(mode=mode, source=source) * graph_weight
        reasons.setdefault(file_key, reason)
        self._record_stage_hit(diagnostics, "graph", file_key)

    def _owner_file_promotion_weight(self, *, mode: str, source: str) -> float:
        if source == "support":
            if mode == "docs":
                return 2.5
            if mode == "architecture":
                return 3.0
            if mode == "understand":
                return 4.0
            return 6.0
        if source == "memory":
            if mode == "docs":
                return 2.5
            if mode == "architecture":
                return 3.5
            return 5.0
        if mode in {"docs", "architecture"}:
            return 4.0
        return 6.0

    def _is_support_file(self, file: FileRecord) -> bool:
        return self._is_test(file) or self._is_doc(file) or self._is_config(file)

    def _is_test(self, file: FileRecord) -> bool:
        return "test" in file.tags or file.path.startswith("tests/") or "/test" in file.path

    def _is_doc(self, file: FileRecord) -> bool:
        return file.path.startswith("docs/") or file.language.value == "markdown"

    def _is_config(self, file: FileRecord) -> bool:
        return file.path.startswith("config/") or file.language.value in {"toml", "yaml", "json"}

    def _rerank_support_files(
        self,
        *,
        query: str,
        mode: str,
        scores: dict[str, float],
        reasons: dict[str, str],
    ) -> None:
        lowered = query.lower()
        terms = self._terms(query)
        doc_focused = self._is_doc_focused_query(lowered)
        config_focused = self._is_config_focused_query(lowered)
        test_focused = self._is_test_focused_query(lowered)

        for key in list(scores):
            if not key.startswith("file:"):
                continue
            file_id = int(key.split(":", 1)[1])
            file = self.session.get(FileRecord, file_id)
            if file is None:
                continue

            bonus = 0.0
            path_text = file.path.lower()
            summary_text = (file.summary or "").lower()
            match_count = sum(1 for term in terms if term in path_text or term in summary_text)
            if match_count:
                bonus += min(match_count, 3) * (1.0 if self._is_support_file(file) else 0.4)
            if self._is_doc(file):
                if doc_focused or mode in {"docs", "architecture"}:
                    bonus += 4.0 + min(match_count, 2)
                elif match_count:
                    bonus += 2.0
                if "readme" in path_text and mode in {"understand", "docs", "architecture"}:
                    bonus += 1.5
            if self._is_config(file):
                if config_focused:
                    bonus += 4.5 + min(match_count, 2)
                elif mode in {"docs", "architecture"}:
                    bonus += 2.0
                elif match_count >= 2:
                    bonus += 1.5
            if self._is_test(file) and (test_focused or mode in {"refactor", "bugfix", "testgen"}):
                bonus += 2.5 if test_focused else 2.0

            if bonus <= 0:
                continue
            scores[key] += bonus
            reasons.setdefault(key, "final support-file reranking")

    def _expand_symbols_from_ranked_files(
        self,
        *,
        query: str,
        mode: str,
        scores: dict[str, float],
        reasons: dict[str, str],
        diagnostics: dict[str, dict[str, set[int]]],
    ) -> None:
        aliases = self._query_aliases(query)
        file_candidates = sorted(
            ((int(key.split(":", 1)[1]), score) for key, score in scores.items() if key.startswith("file:")),
            key=lambda item: item[1],
            reverse=True,
        )[:10]
        if not file_candidates:
            return

        file_ids = [file_id for file_id, _ in file_candidates]
        symbols = self.session.query(SymbolRecord).filter(SymbolRecord.file_id.in_(file_ids)).all()
        for symbol in symbols:
            symbol_name = symbol.name.lower()
            qualified_name = (symbol.qualified_name or "").lower()
            if not any(alias == symbol_name or alias in qualified_name or alias in symbol_name for alias in aliases):
                continue

            key = f"symbol:{symbol.id}"
            if key not in scores:
                reasons.setdefault(key, "symbol promoted from ranked file and query alias match")
            scores[key] += self._symbol_from_file_bonus(mode=mode)
            self._record_stage_hit(diagnostics, "graph", key)
            self._promote_symbol_owner_file(
                key=key,
                scores=scores,
                reasons=reasons,
                graph_weight=1.0,
                mode=mode,
                source="symbol",
                reason="owner file promoted from ranked file symbol match",
                diagnostics=diagnostics,
            )

    def _query_aliases(self, query: str) -> set[str]:
        terms = self._terms(query)
        aliases = set(terms)
        for size in (2, 3):
            for index in range(len(terms) - size + 1):
                chunk = terms[index : index + size]
                aliases.add("_".join(chunk))
                aliases.add("".join(chunk))
        return {alias for alias in aliases if len(alias) >= 3}

    def _symbol_from_file_bonus(self, *, mode: str) -> float:
        if mode in {"docs", "architecture"}:
            return 4.0
        if mode in {"refactor", "bugfix", "testgen"}:
            return 6.0
        return 5.0

    def _is_doc_focused_query(self, lowered_query: str) -> bool:
        return any(term in lowered_query for term in ("doc", "docs", "runbook", "decision", "adr", "architecture"))

    def _is_config_focused_query(self, lowered_query: str) -> bool:
        return any(term in lowered_query for term in ("config", "settings", "provider", "providers"))

    def _is_test_focused_query(self, lowered_query: str) -> bool:
        return any(term in lowered_query for term in ("test", "tests", "coverage"))

    def _load_entities(self, model, ordered: list[tuple[str, float]], prefix: str):
        ids = [int(key.split(":")[1]) for key, _ in ordered if key.startswith(f"{prefix}:")]
        if not ids:
            return []
        items = self.session.query(model).filter(model.id.in_(ids)).all()
        items_by_id = {item.id: item for item in items}
        return [items_by_id[item_id] for item_id in ids if item_id in items_by_id]

    def _new_diagnostics(self) -> dict[str, dict[str, set[int]]]:
        stages = ("lexical", "support", "graph", "semantic", "selected", "packed")
        return {stage: {"file": set(), "symbol": set(), "memory": set()} for stage in stages}

    def _record_stage_hit(self, diagnostics: dict[str, dict[str, set[int]]], stage: str, key: str) -> None:
        node_kind, raw_id = key.split(":", 1)
        if node_kind not in diagnostics[stage]:
            return
        diagnostics[stage][node_kind].add(int(raw_id))

    def _record_selected_entities(
        self,
        diagnostics: dict[str, dict[str, set[int]]],
        files: list[FileRecord],
        symbols: list[SymbolRecord],
        memories: list[Memory],
    ) -> None:
        for file in files:
            diagnostics["selected"]["file"].add(file.id)
        for symbol in symbols:
            diagnostics["selected"]["symbol"].add(symbol.id)
        for memory in memories:
            diagnostics["selected"]["memory"].add(memory.id)

    def _record_packed_entities(self, diagnostics: dict[str, dict[str, set[int]]], packed: dict) -> None:
        for file in packed["files"]:
            diagnostics["packed"]["file"].add(file["id"])
        for symbol in packed["symbols"]:
            diagnostics["packed"]["symbol"].add(symbol["id"])
        for memory in packed["memories"]:
            diagnostics["packed"]["memory"].add(memory["id"])

    def _render_diagnostics(
        self,
        diagnostics: dict[str, dict[str, set[int]]],
        *,
        ordered: list[tuple[str, float]],
        reasons: dict[str, str],
    ) -> dict:
        return {
            "stages": {
                stage: {
                    "files": self._serialize_files(ids["file"]),
                    "symbols": self._serialize_symbols(ids["symbol"]),
                    "memories": self._serialize_memories(ids["memory"]),
                }
                for stage, ids in diagnostics.items()
            },
            "ranked_candidates": [
                {"node": key, "score": round(float(score), 3), "reason": reasons.get(key, "retrieved by query pipeline")}
                for key, score in ordered[:50]
            ],
        }

    def _serialize_files(self, ids: set[int]) -> list[dict]:
        if not ids:
            return []
        files = self.session.query(FileRecord).filter(FileRecord.id.in_(ids)).all()
        return sorted(({"id": file.id, "path": file.path} for file in files), key=lambda item: item["path"])

    def _serialize_symbols(self, ids: set[int]) -> list[dict]:
        if not ids:
            return []
        symbols = self.session.query(SymbolRecord).filter(SymbolRecord.id.in_(ids)).all()
        return sorted(
            ({"id": symbol.id, "qualified_name": symbol.qualified_name} for symbol in symbols),
            key=lambda item: item["qualified_name"],
        )

    def _serialize_memories(self, ids: set[int]) -> list[dict]:
        if not ids:
            return []
        memories = self.session.query(Memory).filter(Memory.id.in_(ids)).all()
        return sorted(({"id": memory.id, "title": memory.title} for memory in memories), key=lambda item: item["title"])

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
            scores=[{"node": key, "score": float(score)} for key, score in ordered[:25]],
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
        diagnostics: dict[str, dict[str, set[int]]],
    ) -> None:
        if repo_id is None:
            return

        terms = self._terms(query)
        lowered_query = query.lower()
        doc_focused = any(term in lowered_query for term in ("doc", "docs", "runbook", "decision", "architecture", "adr"))
        config_focused = any(term in lowered_query for term in ("config", "settings", "provider", "providers"))
        test_focused = any(term in lowered_query for term in ("test", "tests", "coverage"))
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
            overlap_terms = [term for term in candidate_terms if term in path_text]
            overlap = bool(overlap_terms)
            imports_primary = any(imported in primary_modules for imported in file.imports)
            is_test = "test" in file.tags or file.path.startswith("tests/") or "/test" in file.path
            is_doc = file.path.startswith("docs/") or file.language.value == "markdown"
            is_config = file.path.startswith("config/") or file.language.value in {"toml", "yaml", "json"}

            if is_test and (imports_primary or overlap) and mode in {"understand", "refactor", "bugfix", "testgen"}:
                boost = 14.0 if test_focused else 12.0
                scores[f"file:{file.id}"] += boost * weight["graph"]
                reasons.setdefault(f"file:{file.id}", "related test expansion")
                self._record_stage_hit(diagnostics, "support", f"file:{file.id}")
            elif is_doc and overlap:
                if doc_focused:
                    boost = 6.0
                elif len(overlap_terms) >= 2 or config_focused:
                    boost = 4.0
                else:
                    boost = 2.5
                scores[f"file:{file.id}"] += boost * weight["graph"]
                reasons.setdefault(f"file:{file.id}", "related documentation expansion")
                self._record_stage_hit(diagnostics, "support", f"file:{file.id}")
            elif is_config and overlap:
                boost = 6.0 if config_focused else 5.0
                scores[f"file:{file.id}"] += boost * weight["graph"]
                reasons.setdefault(f"file:{file.id}", "related config expansion")
                self._record_stage_hit(diagnostics, "support", f"file:{file.id}")

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
                self._record_stage_hit(diagnostics, "support", f"memory:{memory.id}")

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
        elif edge_type == EdgeType.doc_describes_file.value:
            base = 5.5 if mode in {"docs", "architecture"} or any(
                term in query_lower for term in ("doc", "docs", "runbook", "decision", "architecture", "adr", "config")
            ) else 3.0
        elif edge_type == EdgeType.doc_describes_symbol.value:
            base = 5.0 if mode in {"docs", "architecture"} or any(
                term in query_lower for term in ("doc", "docs", "runbook", "decision", "architecture", "adr")
            ) else 2.0
        else:
            base = 3.0

        return max(1.0, base - (hops - 1)) * graph_weight
