from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ariadne_index.models.entities import FileRecord, Memory, SymbolRecord


class LexicalSearchService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def search(self, query: str, repo_id: int | None = None, limit: int = 10) -> dict:
        like = f"%{query}%"
        files_query = self.session.query(FileRecord).filter(
            or_(FileRecord.path.ilike(like), FileRecord.summary.ilike(like))
        )
        symbols_query = self.session.query(SymbolRecord).filter(
            or_(
                SymbolRecord.name.ilike(like),
                SymbolRecord.qualified_name.ilike(like),
                SymbolRecord.docstring.ilike(like),
                SymbolRecord.summary.ilike(like),
            )
        )
        memories_query = self.session.query(Memory).filter(
            or_(Memory.title.ilike(like), Memory.content.ilike(like), Memory.summary.ilike(like))
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
