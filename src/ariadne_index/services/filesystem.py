from __future__ import annotations

import fnmatch
import hashlib
from pathlib import Path


def sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def should_include(relative_path: str, include_globs: list[str], exclude_globs: list[str]) -> bool:
    included = any(fnmatch.fnmatch(relative_path, pattern) for pattern in include_globs)
    excluded = any(fnmatch.fnmatch(relative_path, pattern) for pattern in exclude_globs)
    return included and not excluded


def discover_files(root: Path, include_globs: list[str], exclude_globs: list[str]) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if should_include(relative, include_globs, exclude_globs):
            files.append(path)
    return sorted(files)
