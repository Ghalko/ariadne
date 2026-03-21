from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from ariadne_index.models.entities import FileRecord, Memory, Repo, SymbolRecord


class ContextPacker:
    def __init__(self, session: Session) -> None:
        self.session = session

    def pack(
        self,
        *,
        repo: Repo | None,
        files: list[FileRecord],
        symbols: list[SymbolRecord],
        memories: list[Memory],
        reasons: dict[str, str],
        include_code: bool,
    ) -> dict:
        repo_root = Path(repo.local_path) if repo is not None else None
        file_summaries = [
            {
                "id": file.id,
                "path": file.path,
                "language": file.language.value,
                "summary": file.summary,
                "why": reasons.get(f"file:{file.id}", "retrieved by query pipeline"),
            }
            for file in files
        ]
        symbol_summaries = [
            {
                "id": symbol.id,
                "file_id": symbol.file_id,
                "qualified_name": symbol.qualified_name,
                "type": symbol.symbol_type,
                "lines": [symbol.line_start, symbol.line_end],
                "summary": symbol.summary,
                "why": reasons.get(f"symbol:{symbol.id}", "retrieved by query pipeline"),
            }
            for symbol in symbols
        ]
        packed = {
            "repo": repo.name if repo else None,
            "files": file_summaries,
            "symbols": symbol_summaries,
            "memories": [
                {
                    "id": memory.id,
                    "title": memory.title,
                    "type": memory.memory_type.value,
                    "status": memory.status.value,
                    "summary": memory.summary,
                    "why": reasons.get(f"memory:{memory.id}", "retrieved by query pipeline"),
                }
                for memory in memories
            ],
            "snippets": [],
        }
        if include_code and repo_root is not None:
            for symbol in symbols[:6]:
                file_record = next((item for item in files if item.id == symbol.file_id), None)
                if file_record is None:
                    continue
                snippet = self._snippet(repo_root / file_record.path, symbol.line_start, symbol.line_end)
                packed["snippets"].append(
                    {
                        "file": file_record.path,
                        "symbol": symbol.qualified_name,
                        "lines": [symbol.line_start, symbol.line_end],
                        "code": snippet,
                    }
                )
        return packed

    def _snippet(self, path: Path, line_start: int, line_end: int) -> str:
        if not path.exists():
            return ""
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return "\n".join(lines[line_start - 1 : line_end])
