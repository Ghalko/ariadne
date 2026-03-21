from __future__ import annotations

import re
from pathlib import Path

from ariadne_index.models.enums import FileLanguage
from ariadne_index.parsers.base import ParsedFile, ParsedSymbol

IMPORT_RE = re.compile(r"^\s*import\s+.*?from\s+['\"]([^'\"]+)['\"]", re.MULTILINE)
EXPORT_CONST_RE = re.compile(r"^\s*export\s+const\s+([A-Za-z0-9_]+)", re.MULTILINE)
FUNCTION_RE = re.compile(r"^\s*(?:export\s+)?function\s+([A-Za-z0-9_]+)\s*\((.*?)\)", re.MULTILINE)
CLASS_RE = re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z0-9_]+)", re.MULTILINE)

try:  # pragma: no cover - exercised only when optional dependency is installed
    from tree_sitter_language_pack import get_parser
except ImportError:  # pragma: no cover - fallback compatibility path
    try:
        from tree_sitter_languages import get_parser
    except ImportError:  # pragma: no cover - fallback path is unit tested
        get_parser = None


class TypeScriptParser:
    def parse(self, path: Path, content: str) -> ParsedFile:
        language = FileLanguage.typescript if path.suffix in {".ts", ".tsx"} else FileLanguage.javascript
        parsed = self._parse_with_tree_sitter(path, content, language)
        if parsed is not None:
            return parsed
        return self._parse_with_regex(path, content, language)

    def _parse_with_tree_sitter(self, path: Path, content: str, language: FileLanguage) -> ParsedFile | None:
        if get_parser is None:
            return None
        parser = get_parser("typescript" if language == FileLanguage.typescript else "javascript")
        tree = parser.parse(content.encode("utf-8"))
        root = tree.root_node
        symbols: list[ParsedSymbol] = []
        imports: list[str] = []

        for child in root.children:
            if child.type == "import_statement":
                import_text = content[child.start_byte : child.end_byte]
                match = IMPORT_RE.search(import_text)
                if match:
                    imports.append(match.group(1))
            elif child.type in {"function_declaration", "class_declaration", "lexical_declaration"}:
                line_start = child.start_point[0] + 1
                line_end = child.end_point[0] + 1
                snippet = content[child.start_byte : child.end_byte]
                if child.type == "function_declaration":
                    match = FUNCTION_RE.search(snippet)
                    if match:
                        name = match.group(1)
                        params = match.group(2)
                        symbols.append(
                            ParsedSymbol(
                                name=name,
                                symbol_type="function",
                                line_start=line_start,
                                line_end=line_end,
                                signature=f"function {name}({params})",
                                qualified_name=name,
                                summary=f"{language.value.title()} function {name}",
                            )
                        )
                elif child.type == "class_declaration":
                    match = CLASS_RE.search(snippet)
                    if match:
                        name = match.group(1)
                        symbols.append(
                            ParsedSymbol(
                                name=name,
                                symbol_type="class",
                                line_start=line_start,
                                line_end=line_end,
                                qualified_name=name,
                                summary=f"{language.value.title()} class {name}",
                            )
                        )
                elif child.type == "lexical_declaration":
                    match = EXPORT_CONST_RE.search(snippet)
                    if match:
                        name = match.group(1)
                        symbols.append(
                            ParsedSymbol(
                                name=name,
                                symbol_type="exported_constant",
                                line_start=line_start,
                                line_end=line_end,
                                qualified_name=name,
                                summary=f"Exported constant {name}",
                            )
                        )

        return ParsedFile(
            language=language,
            imports=sorted(set(imports)),
            summary=f"{language.value.title()} module {path.name} with {len(symbols)} exported symbols.",
            symbols=symbols,
            tags=self._infer_tags(path),
        )

    def _parse_with_regex(self, path: Path, content: str, language: FileLanguage) -> ParsedFile:
        imports = sorted(set(match.group(1) for match in IMPORT_RE.finditer(content)))
        symbols: list[ParsedSymbol] = []
        lines = content.splitlines()

        for pattern, symbol_type, formatter in (
            (FUNCTION_RE, "function", lambda name, params: f"function {name}({params})"),
            (CLASS_RE, "class", lambda name, _: f"class {name}"),
            (EXPORT_CONST_RE, "exported_constant", lambda name, _: f"const {name}"),
        ):
            for match in pattern.finditer(content):
                line_no = content[: match.start()].count("\n") + 1
                name = match.group(1)
                params = match.group(2) if pattern is FUNCTION_RE else ""
                symbols.append(
                    ParsedSymbol(
                        name=name,
                        symbol_type=symbol_type,
                        line_start=line_no,
                        line_end=min(len(lines), line_no + 3),
                        signature=formatter(name, params),
                        qualified_name=name,
                        summary=f"{language.value.title()} {symbol_type} {name}",
                    )
                )

        return ParsedFile(
            language=language,
            imports=imports,
            summary=f"{language.value.title()} module {path.name} with {len(symbols)} exported symbols.",
            symbols=symbols,
            tags=self._infer_tags(path),
        )

    def _infer_tags(self, path: Path) -> list[str]:
        lowered = str(path).lower()
        tags = []
        if ".test." in lowered or ".spec." in lowered:
            tags.append("test")
        return tags
