from __future__ import annotations

from pathlib import Path

import pytest

from ariadne_index.bootstrap import build_services
from ariadne_index.db import init_database, session_scope
from ariadne_index.models.entities import Edge, Embedding, FileRecord, Memory, Repo, RetrievalLog, SymbolRecord
from ariadne_index.schemas import MemoryCreate, RepoCreate
from ariadne_index.services.db_migration import init_branch_sqlite, merge_sqlite_databases, migrate_to_sqlite
from ariadne_index.services.uuid_backfill import backfill_uuids


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


def test_init_branch_sqlite_copies_seed_to_branch_named_path(tmp_path: Path) -> None:
    source_path = tmp_path / "seed.sqlite"
    source_path.write_bytes(b"seed")

    result = init_branch_sqlite(
        branch="feature/context work",
        source_path=source_path,
        target_dir=tmp_path / "branches",
    )

    target_path = tmp_path / "branches" / "feature-context-work.sqlite"
    assert result["target"] == str(target_path)
    assert target_path.read_bytes() == b"seed"


def test_merge_sqlite_databases_merges_new_memory_without_binary_conflict(tmp_path: Path) -> None:
    main_url = f"sqlite+pysqlite:///{tmp_path / 'main.sqlite'}"
    branch_url = f"sqlite+pysqlite:///{tmp_path / 'branch.sqlite'}"
    init_database(main_url)
    init_database(branch_url)

    with session_scope(main_url) as session:
        services = build_services(session)
        services["repos"].add_repo(RepoCreate(name="sample", local_path="/tmp/sample"))

    migrate_to_sqlite(source_database_url=main_url, target_path=tmp_path / "branch-copy.sqlite")
    (tmp_path / "branch-copy.sqlite").replace(tmp_path / "branch.sqlite")

    with session_scope(branch_url) as session:
        services = build_services(session)
        repo = services["repos"].get_repo_by_name("sample")
        services["memory"].create_memory(
            MemoryCreate(
                repo_id=repo.id,
                title="Branch memory",
                content="Preserve this branch-local decision.",
                summary="Branch decision",
                memory_type="decision",
            )
        )

    dry_run = merge_sqlite_databases(
        source_path=tmp_path / "branch.sqlite",
        target_path=tmp_path / "main.sqlite",
        dry_run=True,
    )
    assert dry_run["would_insert"]["memories"] == 1

    applied = merge_sqlite_databases(
        source_path=tmp_path / "branch.sqlite",
        target_path=tmp_path / "main.sqlite",
        dry_run=False,
    )
    assert applied["inserted"]["memories"] == 1

    with session_scope(main_url) as session:
        memories = session.query(Memory).all()
        assert [memory.title for memory in memories] == ["Branch memory"]


def test_merge_sqlite_databases_uses_uuid_identity_when_integer_ids_diverge(tmp_path: Path) -> None:
    main_url = f"sqlite+pysqlite:///{tmp_path / 'main.sqlite'}"
    branch_url = f"sqlite+pysqlite:///{tmp_path / 'branch.sqlite'}"
    init_database(main_url)
    init_database(branch_url)

    with session_scope(main_url) as session:
        services = build_services(session)
        repo = services["repos"].add_repo(RepoCreate(name="sample", local_path="/tmp/sample"))
        services["memory"].create_memory(
            MemoryCreate(
                repo_id=repo.id,
                title="Main-only memory",
                content="This takes integer id 1 in main.",
                summary="Main local row",
                memory_type="decision",
            )
        )

    with session_scope(branch_url) as session:
        services = build_services(session)
        repo = services["repos"].add_repo(RepoCreate(name="sample", local_path="/tmp/sample"))
        branch_memory = services["memory"].create_memory(
            MemoryCreate(
                repo_id=repo.id,
                title="Branch-only memory",
                content="This also takes integer id 1 in branch.",
                summary="Branch local row",
                memory_type="decision",
            )
        )
        branch_memory_uuid = branch_memory.uuid

    result = merge_sqlite_databases(
        source_path=tmp_path / "branch.sqlite",
        target_path=tmp_path / "main.sqlite",
        dry_run=False,
    )

    assert result["inserted"]["memories"] == 1
    with session_scope(main_url) as session:
        memories = {memory.title: memory for memory in session.query(Memory).order_by(Memory.title)}
        assert set(memories) == {"Branch-only memory", "Main-only memory"}
        assert memories["Branch-only memory"].uuid == branch_memory_uuid
        assert memories["Branch-only memory"].id != 1


def test_backfill_uuids_populates_graph_addressable_rows(db_session, sample_repo: Path) -> None:
    services = build_services(db_session)
    repo = services["repos"].add_repo(RepoCreate(name="sample", local_path=str(sample_repo)))
    services["indexing"].index_repo(repo)
    counts = backfill_uuids(db_session)

    assert set(counts) >= {"repos", "files", "symbols", "edges", "embeddings", "retrieval_logs"}
    assert db_session.query(Repo).filter(Repo.uuid.is_(None)).count() == 0
    assert db_session.query(FileRecord).filter(FileRecord.uuid.is_(None)).count() == 0
    assert db_session.query(SymbolRecord).filter(SymbolRecord.uuid.is_(None)).count() == 0
    assert db_session.query(Edge).filter(Edge.uuid.is_(None)).count() == 0
    assert db_session.query(Embedding).filter(Embedding.node_uuid.is_(None)).count() == 0
