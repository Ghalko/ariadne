from __future__ import annotations

from pathlib import Path

from ariadne_index.models.enums import FileLanguage
from ariadne_index.parsers.base import ParsedFile


class DocsParser:
    def parse(self, path: Path, content: str) -> ParsedFile:
        suffix = path.suffix.lower()
        language = {
            ".md": FileLanguage.markdown,
            ".json": FileLanguage.json,
            ".yaml": FileLanguage.yaml,
            ".yml": FileLanguage.yaml,
            ".toml": FileLanguage.toml,
        }.get(suffix, FileLanguage.unknown)

        first_nonempty = next((line.strip("# ").strip() for line in content.splitlines() if line.strip()), path.name)
        return ParsedFile(
            language=language,
            imports=[],
            summary=f"{language.value.title()} document {path.name}: {first_nonempty[:120]}",
            symbols=[],
            tags=self._infer_tags(path),
        )

    def _infer_tags(self, path: Path) -> list[str]:
        lowered = str(path).lower()
        tags: list[str] = []
        if "adr" in lowered or "decision" in lowered:
            tags.append("architecture")
        if "readme" in lowered:
            tags.append("docs")
        return tags
