from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARIADNE_", env_file=".env", extra="ignore")

    database_url: str = Field(default="sqlite+pysqlite:///:memory:")
    embedding_dimensions: int = Field(default=24)
    default_include_globs: list[str] = Field(
        default_factory=lambda: [
            "**/*.py",
            "**/*.ts",
            "**/*.tsx",
            "**/*.js",
            "**/*.jsx",
            "**/*.md",
            "**/*.json",
            "**/*.yaml",
            "**/*.yml",
            "**/*.toml",
        ]
    )
    default_exclude_globs: list[str] = Field(
        default_factory=lambda: [
            ".git/**",
            "node_modules/**",
            ".venv/**",
            "venv/**",
            "dist/**",
            "build/**",
            "__pycache__/**",
        ]
    )
    workspace_root: Path = Field(default_factory=Path.cwd)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
