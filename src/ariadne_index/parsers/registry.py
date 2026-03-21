from __future__ import annotations

from pathlib import Path

from ariadne_index.parsers.docs_parser import DocsParser
from ariadne_index.parsers.python_parser import PythonParser
from ariadne_index.parsers.ts_parser import TypeScriptParser


class ParserRegistry:
    def __init__(self) -> None:
        self.python = PythonParser()
        self.ts = TypeScriptParser()
        self.docs = DocsParser()

    def parse(self, path: Path, content: str):
        suffix = path.suffix.lower()
        if suffix == ".py":
            return self.python.parse(path, content)
        if suffix in {".ts", ".tsx", ".js", ".jsx"}:
            return self.ts.parse(path, content)
        return self.docs.parse(path, content)
