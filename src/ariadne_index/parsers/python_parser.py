from __future__ import annotations

import ast
from pathlib import Path

from ariadne_index.models.enums import FileLanguage
from ariadne_index.parsers.base import ParsedFile, ParsedSymbol


class PythonParser:
    language = FileLanguage.python

    def parse(self, path: Path, content: str) -> ParsedFile:
        tree = ast.parse(content)
        imports: list[str] = []
        symbols: list[ParsedSymbol] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imports.append(module)

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                symbols.append(
                    ParsedSymbol(
                        name=node.name,
                        symbol_type="class",
                        line_start=node.lineno,
                        line_end=getattr(node, "end_lineno", node.lineno),
                        docstring=ast.get_docstring(node),
                        qualified_name=node.name,
                        summary=self._summarize_node(node),
                    )
                )
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbols.append(
                            ParsedSymbol(
                                name=member.name,
                                symbol_type="method",
                                line_start=member.lineno,
                                line_end=getattr(member, "end_lineno", member.lineno),
                                signature=self._function_signature(member),
                                docstring=ast.get_docstring(member),
                                qualified_name=f"{node.name}.{member.name}",
                                parent_name=node.name,
                                summary=self._summarize_node(member),
                            )
                        )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(
                    ParsedSymbol(
                        name=node.name,
                        symbol_type="function",
                        line_start=node.lineno,
                        line_end=getattr(node, "end_lineno", node.lineno),
                        signature=self._function_signature(node),
                        docstring=ast.get_docstring(node),
                        qualified_name=node.name,
                        summary=self._summarize_node(node),
                    )
                )

        return ParsedFile(
            language=self.language,
            imports=sorted(set(filter(None, imports))),
            summary=self._summarize_module(path, symbols, imports),
            symbols=symbols,
            tags=self._infer_tags(path),
        )

    def _function_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        args = [arg.arg for arg in node.args.args]
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        return f"{prefix} {node.name}({', '.join(args)})"

    def _summarize_node(self, node: ast.AST) -> str:
        if isinstance(node, ast.ClassDef):
            return f"Python class {node.name}"
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return f"Python callable {node.name}"
        return "Python symbol"

    def _summarize_module(self, path: Path, symbols: list[ParsedSymbol], imports: list[str]) -> str:
        sample_symbols = ", ".join(symbol.name for symbol in symbols[:3])
        symbol_clause = f" Key symbols: {sample_symbols}." if sample_symbols else ""
        return (
            f"Python module {path.name} with {len(symbols)} top-level symbols "
            f"and {len(set(filter(None, imports)))} imports.{symbol_clause}"
        )

    def _infer_tags(self, path: Path) -> list[str]:
        tags: list[str] = []
        lowered = str(path).lower()
        if "test" in lowered:
            tags.append("test")
        if "config" in lowered or path.name.startswith("settings"):
            tags.append("config")
        return tags
