from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from sqlalchemy import delete, select, update

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


def current_git_branch(*, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    branch = completed.stdout.strip()
    if not branch:
        raise ValueError("could not determine current git branch")
    return branch


def branch_sqlite_path(branch: str, *, target_dir: Path = Path("seed/branches")) -> Path:
    return target_dir / f"{safe_branch_filename(branch)}.sqlite"


def safe_branch_filename(branch: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", branch.strip().replace("/", "-"))
    cleaned = cleaned.strip(".-")
    if not cleaned:
        raise ValueError("branch name does not produce a safe filename")
    return cleaned


def init_branch_sqlite(
    *,
    branch: str,
    source_path: Path = Path("seed/ariadne.sqlite"),
    target_dir: Path = Path("seed/branches"),
    overwrite: bool = False,
) -> dict:
    if not source_path.exists():
        raise FileNotFoundError(f"{source_path} does not exist")
    target_path = branch_sqlite_path(branch, target_dir=target_dir)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists() and not overwrite:
        raise FileExistsError(f"{target_path} already exists; pass overwrite=True to replace it")
    shutil.copy2(source_path, target_path)
    return {
        "branch": branch,
        "source": str(source_path),
        "target": str(target_path),
        "database_url": f"sqlite+pysqlite:///{target_path}",
        "bytes": target_path.stat().st_size,
    }


def merge_sqlite_databases(
    *,
    source_path: Path,
    target_path: Path,
    include_retrieval_logs: bool = False,
    dry_run: bool = True,
) -> dict:
    if not source_path.exists():
        raise FileNotFoundError(f"{source_path} does not exist")
    if not target_path.exists():
        raise FileNotFoundError(f"{target_path} does not exist")

    source_engine = build_engine(f"sqlite+pysqlite:///{source_path}")
    target_engine = build_engine(f"sqlite+pysqlite:///{target_path}")
    counts = {
        "repos": 0,
        "files": 0,
        "symbols": 0,
        "memories": 0,
        "edges": 0,
        "embeddings": 0,
        "retrieval_logs": 0,
    }
    conflicts: list[dict] = []

    with source_engine.connect() as source, target_engine.begin() as target:
        repo_id_map = _merge_repos(source, target, dry_run=dry_run, conflicts=conflicts, counts=counts)
        file_id_map = _merge_files(source, target, repo_id_map=repo_id_map, dry_run=dry_run, counts=counts)
        symbol_id_map = _merge_symbols(source, target, repo_id_map=repo_id_map, file_id_map=file_id_map, dry_run=dry_run, counts=counts)
        memory_id_map = _merge_memories(source, target, repo_id_map=repo_id_map, dry_run=dry_run, counts=counts)
        node_maps = {
            "repo": repo_id_map,
            "file": file_id_map,
            "symbol": symbol_id_map,
            "memory": memory_id_map,
        }
        _merge_edges(source, target, repo_id_map=repo_id_map, node_maps=node_maps, dry_run=dry_run, counts=counts)
        _merge_embeddings(source, target, repo_id_map=repo_id_map, node_maps=node_maps, dry_run=dry_run, counts=counts)
        if include_retrieval_logs:
            _merge_retrieval_logs(source, target, repo_id_map=repo_id_map, dry_run=dry_run, counts=counts)

    return {
        "dry_run": dry_run,
        "source": str(source_path),
        "target": str(target_path),
        "include_retrieval_logs": include_retrieval_logs,
        "would_insert" if dry_run else "inserted": counts,
        "conflicts": conflicts,
    }


def _merge_repos(source, target, *, dry_run: bool, conflicts: list[dict], counts: dict[str, int]) -> dict[int, int]:
    table = Base.metadata.tables["repos"]
    target_by_name = {row._mapping["name"]: row._mapping for row in target.execute(select(table))}
    id_map: dict[int, int] = {}
    for row in source.execute(select(table).order_by(table.c.id)):
        source_row = dict(row._mapping)
        target_row = target_by_name.get(source_row["name"])
        if target_row is not None:
            id_map[source_row["id"]] = target_row["id"]
            if target_row["local_path"] != source_row["local_path"]:
                conflicts.append(
                    {
                        "table": "repos",
                        "key": source_row["name"],
                        "reason": "same repo name with different local_path",
                        "source": source_row["local_path"],
                        "target": target_row["local_path"],
                    }
                )
            continue
        id_map[source_row["id"]] = _insert_row(target, table, source_row, dry_run=dry_run)
        counts["repos"] += 1
    return id_map


def _merge_files(source, target, *, repo_id_map: dict[int, int], dry_run: bool, counts: dict[str, int]) -> dict[int, int]:
    table = Base.metadata.tables["files"]
    target_by_key = {(row._mapping["repo_id"], row._mapping["path"]): row._mapping["id"] for row in target.execute(select(table))}
    id_map: dict[int, int] = {}
    for row in source.execute(select(table).order_by(table.c.id)):
        source_row = dict(row._mapping)
        source_row["repo_id"] = repo_id_map[source_row["repo_id"]]
        key = (source_row["repo_id"], source_row["path"])
        existing_id = target_by_key.get(key)
        if existing_id is not None:
            id_map[row._mapping["id"]] = existing_id
            continue
        id_map[row._mapping["id"]] = _insert_row(target, table, source_row, dry_run=dry_run)
        target_by_key[key] = id_map[row._mapping["id"]]
        counts["files"] += 1
    return id_map


def _merge_symbols(
    source,
    target,
    *,
    repo_id_map: dict[int, int],
    file_id_map: dict[int, int],
    dry_run: bool,
    counts: dict[str, int],
) -> dict[int, int]:
    table = Base.metadata.tables["symbols"]
    target_by_key = {
        (row._mapping["file_id"], row._mapping["name"], row._mapping["line_start"], row._mapping["line_end"]): row._mapping["id"]
        for row in target.execute(select(table))
    }
    id_map: dict[int, int] = {}
    pending_parent_updates: list[tuple[int, int | None]] = []
    for row in source.execute(select(table).order_by(table.c.id)):
        original = dict(row._mapping)
        source_row = dict(original)
        source_row["repo_id"] = repo_id_map[source_row["repo_id"]]
        source_row["file_id"] = file_id_map[source_row["file_id"]]
        source_row["parent_symbol_id"] = None
        key = (source_row["file_id"], source_row["name"], source_row["line_start"], source_row["line_end"])
        existing_id = target_by_key.get(key)
        if existing_id is not None:
            id_map[original["id"]] = existing_id
            continue
        inserted_id = _insert_row(target, table, source_row, dry_run=dry_run)
        id_map[original["id"]] = inserted_id
        target_by_key[key] = inserted_id
        pending_parent_updates.append((inserted_id, original["parent_symbol_id"]))
        counts["symbols"] += 1

    if not dry_run:
        for target_symbol_id, source_parent_id in pending_parent_updates:
            if source_parent_id is None or source_parent_id not in id_map:
                continue
            target.execute(update(table).where(table.c.id == target_symbol_id).values(parent_symbol_id=id_map[source_parent_id]))
    return id_map


def _merge_memories(source, target, *, repo_id_map: dict[int, int], dry_run: bool, counts: dict[str, int]) -> dict[int, int]:
    table = Base.metadata.tables["memories"]
    target_by_key = {_memory_key(row._mapping): row._mapping["id"] for row in target.execute(select(table))}
    id_map: dict[int, int] = {}
    for row in source.execute(select(table).order_by(table.c.id)):
        source_row = dict(row._mapping)
        if source_row["repo_id"] is not None:
            source_row["repo_id"] = repo_id_map[source_row["repo_id"]]
        key = _memory_key(source_row)
        existing_id = target_by_key.get(key)
        if existing_id is not None:
            id_map[row._mapping["id"]] = existing_id
            continue
        id_map[row._mapping["id"]] = _insert_row(target, table, source_row, dry_run=dry_run)
        target_by_key[key] = id_map[row._mapping["id"]]
        counts["memories"] += 1
    return id_map


def _merge_edges(source, target, *, repo_id_map: dict[int, int], node_maps: dict[str, dict[int, int]], dry_run: bool, counts: dict[str, int]) -> None:
    table = Base.metadata.tables["edges"]
    target_keys = {_edge_key(row._mapping) for row in target.execute(select(table))}
    for row in source.execute(select(table).order_by(table.c.id)):
        source_row = dict(row._mapping)
        source_row["repo_id"] = repo_id_map.get(source_row["repo_id"]) if source_row["repo_id"] is not None else None
        source_row["from_node_id"] = node_maps.get(source_row["from_node_kind"], {}).get(source_row["from_node_id"])
        source_row["to_node_id"] = node_maps.get(source_row["to_node_kind"], {}).get(source_row["to_node_id"])
        if source_row["from_node_id"] is None or source_row["to_node_id"] is None:
            continue
        key = _edge_key(source_row)
        if key in target_keys:
            continue
        _insert_row(target, table, source_row, dry_run=dry_run)
        target_keys.add(key)
        counts["edges"] += 1


def _merge_embeddings(source, target, *, repo_id_map: dict[int, int], node_maps: dict[str, dict[int, int]], dry_run: bool, counts: dict[str, int]) -> None:
    table = Base.metadata.tables["embeddings"]
    target_keys = {
        (row._mapping["node_kind"], row._mapping["node_id"], row._mapping["embedding_role"])
        for row in target.execute(select(table.c.node_kind, table.c.node_id, table.c.embedding_role))
    }
    for row in source.execute(select(table).order_by(table.c.id)):
        source_row = dict(row._mapping)
        source_row["repo_id"] = repo_id_map.get(source_row["repo_id"]) if source_row["repo_id"] is not None else None
        source_row["node_id"] = node_maps.get(source_row["node_kind"], {}).get(source_row["node_id"])
        if source_row["node_id"] is None:
            continue
        key = (source_row["node_kind"], source_row["node_id"], source_row["embedding_role"])
        if key in target_keys:
            continue
        _insert_row(target, table, source_row, dry_run=dry_run)
        target_keys.add(key)
        counts["embeddings"] += 1


def _merge_retrieval_logs(source, target, *, repo_id_map: dict[int, int], dry_run: bool, counts: dict[str, int]) -> None:
    table = Base.metadata.tables["retrieval_logs"]
    target_keys = {
        (row._mapping["repo_id"], row._mapping["query_text"], row._mapping["mode"], row._mapping["created_at"])
        for row in target.execute(select(table.c.repo_id, table.c.query_text, table.c.mode, table.c.created_at))
    }
    for row in source.execute(select(table).order_by(table.c.id)):
        source_row = dict(row._mapping)
        if source_row["repo_id"] is not None:
            source_row["repo_id"] = repo_id_map.get(source_row["repo_id"])
        key = (source_row["repo_id"], source_row["query_text"], source_row["mode"], source_row["created_at"])
        if key in target_keys:
            continue
        _insert_row(target, table, source_row, dry_run=dry_run)
        target_keys.add(key)
        counts["retrieval_logs"] += 1


def _insert_row(connection, table, row: dict[str, Any], *, dry_run: bool) -> int:
    if dry_run:
        return row["id"]
    insert_row = {_key: _portable_value(value) for _key, value in row.items()}
    insert_row.pop("id", None)
    result = connection.execute(table.insert().values(**insert_row))
    return int(result.inserted_primary_key[0])


def _memory_key(row) -> tuple:
    return (
        row["repo_id"],
        row["title"],
        row["content"],
        row["summary"],
        row["memory_type"],
        row["source"],
    )


def _edge_key(row) -> tuple:
    return (
        row["repo_id"],
        row["from_node_kind"],
        row["from_node_id"],
        row["to_node_kind"],
        row["to_node_id"],
        row["edge_type"],
        json.dumps(row["metadata_json"] or {}, sort_keys=True, default=str),
    )
