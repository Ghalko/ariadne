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

        return {
            "files": list(files_query.limit(limit)),
            "symbols": list(symbols_query.limit(limit)),
            "memories": list(memories_query.limit(limit)),
        }

    def _terms(self, query: str) -> list[str]:
        terms = [term for term in re.split(r"\W+", query) if len(term) >= 3]
        return terms or [query]

    def _filters(self, *columns, terms: list[str]):
        filters = []
        for term in terms:
            like = f"%{term}%"
            filters.extend(column.ilike(like) for column in columns)
        return filters
