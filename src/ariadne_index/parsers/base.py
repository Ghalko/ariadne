from __future__ import annotations

from dataclasses import dataclass, field

from ariadne_index.models.enums import FileLanguage


@dataclass(slots=True)
class ParsedSymbol:
    name: str
    symbol_type: str
    line_start: int
    line_end: int
    signature: str | None = None
    docstring: str | None = None
    qualified_name: str | None = None
    parent_name: str | None = None
    summary: str | None = None


@dataclass(slots=True)
class ParsedFile:
    language: FileLanguage
    imports: list[str] = field(default_factory=list)
    summary: str | None = None
    symbols: list[ParsedSymbol] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
