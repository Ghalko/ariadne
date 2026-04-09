from __future__ import annotations

import re

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ariadne_index.models.entities import FileRecord, Memory, SymbolRecord


class LexicalSearchService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def search(self, query: str, repo_id: int | None = None, limit: int = 10) -> dict:
        terms = self._terms(query)
        file_filters = self._filters(FileRecord.path, FileRecord.summary, terms=terms)
        symbol_filters = self._filters(
            SymbolRecord.name,
            SymbolRecord.qualified_name,
            SymbolRecord.docstring,
            SymbolRecord.summary,
            terms=terms,
        )
        memory_filters = self._filters(Memory.title, Memory.content, Memory.summary, terms=terms)

        files_query = self.session.query(FileRecord).filter(
            or_(*file_filters)
        )
        symbols_query = self.session.query(SymbolRecord).filter(
            or_(*symbol_filters)
        )
        memories_query = self.session.query(Memory).filter(
            or_(*memory_filters)
        )

        if repo_id is not None:
            files_query = files_query.filter(FileRecord.repo_id == repo_id)
            symbols_query = symbols_query.filter(SymbolRecord.repo_id == repo_id)
            memories_query = memories_query.filter(or_(Memory.repo_id == repo_id, Memory.repo_id.is_(None)))

        files = self._rank_files(list(files_query.all()), terms=terms)[:limit]
        symbols = self._rank_symbols(list(symbols_query.all()), terms=terms)[:limit]
        memories = self._rank_memories(list(memories_query.all()), terms=terms)[:limit]

        return {"files": files, "symbols": symbols, "memories": memories}

    def _terms(self, query: str) -> list[str]:
        base_terms = [term.lower() for term in re.split(r"\W+", query) if len(term) >= 3]
        expanded: list[str] = []
        seen: set[str] = set()
        for term in base_terms or [query.lower()]:
            for variant in self._expand_term(term):
                if variant in seen or len(variant) < 3:
                    continue
                seen.add(variant)
                expanded.append(variant)
        return expanded

    def _filters(self, *columns, terms: list[str]):
        filters = []
        for term in terms:
            like = f"%{term}%"
            filters.extend(column.ilike(like) for column in columns)
        return filters

    def _expand_term(self, term: str) -> list[str]:
        variants = [term]
        if term.endswith("ies") and len(term) > 4:
            variants.append(f"{term[:-3]}y")
        if term.endswith("s") and len(term) > 4:
            variants.append(term[:-1])
        else:
            variants.append(f"{term}s")
        if term.endswith("ing") and len(term) > 5:
            variants.append(term[:-3])
        if term.endswith("ed") and len(term) > 4:
            variants.append(term[:-2])
        return variants

    def _rank_files(self, files: list[FileRecord], *, terms: list[str]) -> list[FileRecord]:
        def score(file: FileRecord) -> tuple[int, str]:
            path = file.path.lower()
            summary = (file.summary or "").lower()
            basename = path.rsplit("/", 1)[-1]
            score = 0
            for term in terms:
                if term in path:
                    score += 6 if basename.startswith(term) else 4
                if term in summary:
                    score += 3
                if f"/{term}/" in f"/{path}/":
                    score += 2
            return (score, file.path)

        return sorted(files, key=score, reverse=True)

    def _rank_symbols(self, symbols: list[SymbolRecord], *, terms: list[str]) -> list[SymbolRecord]:
        def score(symbol: SymbolRecord) -> tuple[int, str]:
            name = symbol.name.lower()
            qualified = (symbol.qualified_name or "").lower()
            summary = (symbol.summary or "").lower()
            docstring = (symbol.docstring or "").lower()
            score = 0
            for term in terms:
                if term == name:
                    score += 10
                if term in name:
                    score += 7
                if term in qualified:
                    score += 5
                if term in summary:
                    score += 3
                if term in docstring:
                    score += 2
            return (score, symbol.qualified_name or symbol.name)

        return sorted(symbols, key=score, reverse=True)

    def _rank_memories(self, memories: list[Memory], *, terms: list[str]) -> list[Memory]:
        def score(memory: Memory) -> tuple[int, str]:
            title = memory.title.lower()
            summary = (memory.summary or "").lower()
            content = memory.content.lower()
            score = 0
            for term in terms:
                if term in title:
                    score += 7
                if term in summary:
                    score += 4
                if term in content:
                    score += 2
            return (score, memory.title)

        return sorted(memories, key=score, reverse=True)
