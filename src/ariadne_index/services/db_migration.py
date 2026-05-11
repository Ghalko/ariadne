from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import delete, select

from ariadne_index.db import build_engine
from ariadne_index.models.base import Base


ARIADNE_TABLE_COPY_ORDER = [
    "repos",
    "files",
    "symbols",
    "memories",
    "edges",
    "embeddings",
    "retrieval_logs",
]


def migrate_to_sqlite(
    *,
    source_database_url: str,
    target_database_url: str | None = None,
    target_path: Path | None = None,
    overwrite: bool = False,
) -> dict:
    if target_database_url is None:
        if target_path is None:
            raise ValueError("target_path or target_database_url is required")
        target_database_url = f"sqlite+pysqlite:///{target_path}"
    if not target_database_url.startswith("sqlite"):
        raise ValueError("target database must be SQLite")

    if target_path is not None:
        if target_path.exists() and not overwrite:
            raise FileExistsError(f"{target_path} already exists; pass overwrite=True to replace it")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists() and overwrite:
            target_path.unlink()

    source_engine = build_engine(source_database_url)
    target_engine = build_engine(target_database_url)
    if source_engine.dialect.name == target_engine.dialect.name and str(source_engine.url) == str(target_engine.url):
        raise ValueError("source and target database URLs must be different")

    Base.metadata.create_all(target_engine)
    copied: dict[str, int] = {}

    with source_engine.connect() as source, target_engine.begin() as target:
        if overwrite and target_path is None:
            for table_name in reversed(ARIADNE_TABLE_COPY_ORDER):
                table = Base.metadata.tables[table_name]
                target.execute(delete(table))

        for table_name in ARIADNE_TABLE_COPY_ORDER:
            table = Base.metadata.tables[table_name]
            rows = [
                {column.name: _portable_value(row._mapping[column.name]) for column in table.columns}
                for row in source.execute(select(table).order_by(table.c.id))
            ]
            if rows:
                target.execute(table.insert(), rows)
            copied[table_name] = len(rows)

    return {
        "source_dialect": source_engine.dialect.name,
        "target_dialect": target_engine.dialect.name,
        "target_database_url": target_database_url,
        "copied": copied,
        "total_rows": sum(copied.values()),
    }


def _portable_value(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    return value
