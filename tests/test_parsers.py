from __future__ import annotations

from pathlib import Path

from ariadne_index.models.enums import FileLanguage
from ariadne_index.parsers.python_parser import PythonParser
from ariadne_index.parsers.ts_parser import TypeScriptParser


def test_python_parser_extracts_symbols() -> None:
    parser = PythonParser()
    content = (
        "class RetryService:\n"
        "    def execute(self, payload):\n"
        "        return payload\n\n"
        "def retry_logic(payload):\n"
        "    return payload\n"
    )
    parsed = parser.parse(Path("service.py"), content)
    names = {symbol.qualified_name for symbol in parsed.symbols}
    assert parsed.language == FileLanguage.python
    assert "RetryService" in names
    assert "RetryService.execute" in names
    assert "retry_logic" in names


def test_typescript_parser_fallback_extracts_exports() -> None:
    parser = TypeScriptParser()
    content = (
        "import { api } from './api';\n"
        "export function retrySync(payload: string) { return api(payload); }\n"
        "export const RETRY_LIMIT = 3;\n"
    )
    parsed = parser.parse(Path("sync.ts"), content)
    names = {symbol.name for symbol in parsed.symbols}
    assert parsed.language == FileLanguage.typescript
    assert "./api" in parsed.imports
    assert "retrySync" in names
    assert "RETRY_LIMIT" in names
