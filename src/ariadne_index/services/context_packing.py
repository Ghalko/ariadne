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
        files = self._balanced_files(files)
        symbols = symbols[:4]
        memories = memories[:2]
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

    def _balanced_files(self, files: list[FileRecord]) -> list[FileRecord]:
        code_files = [file for file in files if not self._is_support_file(file)]
        support_files = [file for file in files if self._is_support_file(file)]
        tests = [file for file in support_files if self._is_test(file)]
        docs = [file for file in support_files if self._is_doc(file)]
        configs = [file for file in support_files if self._is_config(file)]

        selected: list[FileRecord] = []
        selected.extend(code_files[:3])
        selected.extend(tests[:2])
        selected.extend(docs[:2])
        selected.extend(configs[:1])

        seen: set[int] = set()
        deduped: list[FileRecord] = []
        for file in [*selected, *files]:
            if file.id in seen:
                continue
            seen.add(file.id)
            deduped.append(file)
        return deduped[:8]

    def _is_support_file(self, file: FileRecord) -> bool:
        return self._is_test(file) or self._is_doc(file) or self._is_config(file)

    def _is_test(self, file: FileRecord) -> bool:
        return "test" in file.tags or file.path.startswith("tests/") or "/test" in file.path

    def _is_doc(self, file: FileRecord) -> bool:
        return file.path.startswith("docs/") or file.language.value == "markdown"

    def _is_config(self, file: FileRecord) -> bool:
        return file.path.startswith("config/") or file.language.value in {"toml", "yaml", "json"}

    def _snippet(self, path: Path, line_start: int, line_end: int) -> str:
        if not path.exists():
            return ""
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return "\n".join(lines[line_start - 1 : line_end])
