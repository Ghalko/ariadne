from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from ariadne_index.models.entities import FileRecord, Memory, Repo, SymbolRecord
from ariadne_index.services.secrets import redact_secrets


class ContextPacker:
    def __init__(self, session: Session) -> None:
        self.session = session

    def pack(
        self,
        *,
        repo: Repo | None,
        mode: str,
        query: str,
        files: list[FileRecord],
        symbols: list[SymbolRecord],
        memories: list[Memory],
        reasons: dict[str, str],
        include_code: bool,
    ) -> dict:
        repo_root = Path(repo.local_path) if repo is not None else None
        files = self._balanced_files(files, mode=mode, query=query)
        symbols = symbols[: self._symbol_limit(mode)]
        memories = memories[: self._memory_limit(mode)]
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

    def _balanced_files(self, files: list[FileRecord], *, mode: str, query: str) -> list[FileRecord]:
        code_files = [file for file in files if not self._is_support_file(file)]
        support_files = [file for file in files if self._is_support_file(file)]
        tests = [file for file in support_files if self._is_test(file)]
        docs = [file for file in support_files if self._is_doc(file)]
        configs = [file for file in support_files if self._is_config(file)]

        code_limit, test_limit, doc_limit, config_limit = self._file_mix(mode, query=query)

        selected: list[FileRecord] = []
        selected.extend(code_files[:code_limit])
        selected.extend(tests[:test_limit])
        selected.extend(docs[:doc_limit])
        selected.extend(configs[:config_limit])

        seen: set[int] = set()
        deduped: list[FileRecord] = []
        for file in [*selected, *files]:
            if file.id in seen:
                continue
            seen.add(file.id)
            deduped.append(file)
        return deduped[:8]

    def _file_mix(self, mode: str, *, query: str) -> tuple[int, int, int, int]:
        if mode == "docs":
            base = [2, 1, 3, 2]
        elif mode == "architecture":
            base = [2, 0, 3, 1]
        elif mode in {"refactor", "bugfix", "testgen"}:
            base = [4, 2, 1, 1]
        else:
            base = [3, 1, 2, 1]

        lowered = query.lower()
        if any(term in lowered for term in ("doc", "docs", "runbook", "decision", "adr", "architecture")):
            base[2] = max(base[2], 2 if mode in {"refactor", "bugfix"} else 3)
            base[0] = max(2, base[0] - 1)
        if any(term in lowered for term in ("config", "settings", "provider", "providers")):
            base[3] = max(base[3], 2 if mode in {"docs", "architecture", "understand"} else 1)
            if mode in {"understand", "docs", "architecture"}:
                base[2] = max(base[2], 2)
        if any(term in lowered for term in ("test", "tests", "coverage")):
            base[1] = max(base[1], 2)

        total = sum(base)
        while total > 8:
            for index in (0, 1, 2, 3):
                minimum = 2 if index == 0 else 1 if base[index] > 0 else 0
                if base[index] > minimum:
                    base[index] -= 1
                    total -= 1
                    break
            else:
                break
        return tuple(base)

    def _symbol_limit(self, mode: str) -> int:
        if mode in {"docs", "architecture"}:
            return 4
        if mode in {"refactor", "bugfix", "testgen"}:
            return 6
        return 5

    def _memory_limit(self, mode: str) -> int:
        if mode in {"docs", "architecture", "refactor"}:
            return 3
        return 2

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
        return redact_secrets("\n".join(lines[line_start - 1 : line_end])) or ""
