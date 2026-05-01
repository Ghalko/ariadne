from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARIADNE_", env_file=".env", extra="ignore")

    database_url: str = Field(default="sqlite+pysqlite:///:memory:")
    embedding_provider: str = Field(default="auto")
    embedding_model: str = Field(default="text-embedding-3-small")
    embedding_dimensions: int = Field(default=1024)
    strict_db_compatibility: bool = Field(default=False)
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "ARIADNE_OPENAI_API_KEY"),
    )
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
            "**/.git/**",
            "node_modules/**",
            "**/node_modules/**",
            ".venv/**",
            "**/.venv/**",
            "venv/**",
            "**/venv/**",
            "dist/**",
            "**/dist/**",
            "build/**",
            "**/build/**",
            "__pycache__/**",
            "**/__pycache__/**",
            ".pytest_cache/**",
            "**/.pytest_cache/**",
        ]
    )
    workspace_root: Path = Field(default_factory=Path.cwd)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
