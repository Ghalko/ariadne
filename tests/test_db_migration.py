from __future__ import annotations

from pathlib import Path

import pytest

from ariadne_index.bootstrap import build_services
from ariadne_index.db import init_database, session_scope
from ariadne_index.models.entities import Edge, Embedding, FileRecord, Memory, Repo, RetrievalLog, SymbolRecord
from ariadne_index.schemas import MemoryCreate, RepoCreate
from ariadne_index.services.db_migration import migrate_to_sqlite


def test_migrate_to_sqlite_copies_ariadne_tables(tmp_path: Path, sample_repo: Path) -> None:
    source_url = f"sqlite+pysqlite:///{tmp_path / 'source.db'}"
    target_path = tmp_path / "target.db"
    init_database(source_url)

    with session_scope(source_url) as session:
        services = build_services(session)
        repo = services["repos"].add_repo(RepoCreate(name="sample", local_path=str(sample_repo)))
        services["indexing"].index_repo(repo)
        services["memory"].create_memory(
            MemoryCreate(
                repo_id=repo.id,
                title="Migration note",
                content="Copy this durable memory.",
                summary="Migration memory",
                memory_type="decision",
            )
        )
        services["retrieval"].retrieve(query="retry logic", mode="understand", repo=repo, include_code=False)

    result = migrate_to_sqlite(source_database_url=source_url, target_path=target_path)

    assert result["target_dialect"] == "sqlite"
    assert result["copied"]["repos"] == 1
    assert result["copied"]["files"] == 6
    assert result["copied"]["memories"] == 1
    assert target_path.exists()

    with session_scope(f"sqlite+pysqlite:///{target_path}") as session:
        assert session.query(Repo).count() == 1
        assert session.query(FileRecord).count() == 6
        assert session.query(SymbolRecord).count() > 0
        assert session.query(Edge).count() > 0
        assert session.query(Embedding).count() > 0
        assert session.query(Memory).count() == 1
        assert session.query(RetrievalLog).count() == 1
        assert session.query(Repo).one().name == "sample"


def test_migrate_to_sqlite_refuses_existing_target_without_overwrite(tmp_path: Path) -> None:
    source_url = f"sqlite+pysqlite:///{tmp_path / 'source.db'}"
    target_path = tmp_path / "target.db"
    init_database(source_url)
    target_path.write_text("not a database", encoding="utf-8")

    with pytest.raises(FileExistsError):
        migrate_to_sqlite(source_database_url=source_url, target_path=target_path)
