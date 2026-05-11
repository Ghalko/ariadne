from __future__ import annotations

import json
from pathlib import Path

import typer

from ariadne_index.bootstrap import build_services
from ariadne_index.config import get_settings
from ariadne_index.db import build_engine, database_diagnostics, init_database, session_scope
from ariadne_index.models.entities import RetrievalLog
from ariadne_index.schemas import MemoryCreate, MemoryLinkCreate, RepoCreate
from ariadne_index.services.db_migration import migrate_to_sqlite

app = typer.Typer(help="Repo indexing, graph retrieval, and durable memory.")
memory_app = typer.Typer(help="Memory CRUD commands.")
app.add_typer(memory_app, name="memory")


@app.command()
def init(database_url: str | None = typer.Option(default=None, help="Override database URL")) -> None:
    init_database(database_url)
    typer.echo("database initialized")


@app.command("add-repo")
def add_repo(
    path: Path,
    name: str = typer.Option(..., help="Logical repository name"),
    database_url: str | None = typer.Option(default=None),
) -> None:
    with session_scope(database_url) as session:
        services = build_services(session)
        repo = services["repos"].add_repo(RepoCreate(name=name, local_path=str(path)))
        typer.echo(json.dumps({"id": repo.id, "name": repo.name, "path": repo.local_path}, indent=2))


@app.command()
def repos(database_url: str | None = typer.Option(default=None)) -> None:
    with session_scope(database_url) as session:
        services = build_services(session)
        payload = [
            {
                "id": repo.id,
                "name": repo.name,
                "path": repo.local_path,
                "branch": repo.active_branch,
                "commit": repo.current_commit_sha,
            }
            for repo in services["repos"].list_repos()
        ]
        typer.echo(json.dumps(payload, indent=2))


@app.command()
def index(
    repo_name: str,
    database_url: str | None = typer.Option(default=None),
) -> None:
    with session_scope(database_url) as session:
        services = build_services(session)
        repo = services["repos"].get_repo_by_name(repo_name)
        result = services["indexing"].index_repo(repo)
        typer.echo(json.dumps(result, indent=2))


@app.command()
def reindex(
    repo_name: str,
    database_url: str | None = typer.Option(default=None),
) -> None:
    with session_scope(database_url) as session:
        services = build_services(session)
        repo = services["repos"].get_repo_by_name(repo_name)
        result = services["indexing"].index_repo(repo)
        typer.echo(json.dumps({"mode": "incremental", **result}, indent=2))


@app.command()
def search(
    query: str,
    repo_name: str | None = typer.Option(default=None),
    database_url: str | None = typer.Option(default=None),
) -> None:
    with session_scope(database_url) as session:
        services = build_services(session)
        repo = services["repos"].get_repo_by_name(repo_name) if repo_name else None
        payload = services["retrieval"].lexical.search(query, repo_id=repo.id if repo else None)
        typer.echo(
            json.dumps(
                {
                    "files": [file.path for file in payload["files"]],
                    "symbols": [symbol.qualified_name for symbol in payload["symbols"]],
                    "memories": [memory.title for memory in payload["memories"]],
                },
                indent=2,
            )
        )


@app.command("pack-context")
def pack_context(
    query: str,
    mode: str = typer.Option(default="understand"),
    repo_name: str | None = typer.Option(default=None),
    include_code: bool = typer.Option(default=True),
    database_url: str | None = typer.Option(default=None),
) -> None:
    with session_scope(database_url) as session:
        services = build_services(session)
        repo = services["repos"].get_repo_by_name(repo_name) if repo_name else None
        payload = services["retrieval"].retrieve(
            query=query,
            mode=mode,
            repo=repo,
            include_code=include_code,
        )
        typer.echo(json.dumps(payload["context"], indent=2))


@app.command("graph")
def graph_cmd(
    node_kind: str,
    node_id: int,
    max_hops: int = typer.Option(default=1),
    database_url: str | None = typer.Option(default=None),
) -> None:
    with session_scope(database_url) as session:
        services = build_services(session)
        payload = services["graph"].traverse(start_kind=node_kind, start_id=node_id, max_hops=max_hops)
        typer.echo(json.dumps(payload, indent=2))


@app.command("retrieve")
def retrieve(
    query: str,
    mode: str = typer.Option(default="understand"),
    repo_name: str | None = typer.Option(default=None),
    include_code: bool = typer.Option(default=True),
    database_url: str | None = typer.Option(default=None),
) -> None:
    with session_scope(database_url) as session:
        services = build_services(session)
        repo = services["repos"].get_repo_by_name(repo_name) if repo_name else None
        payload = services["retrieval"].retrieve(
            query=query,
            mode=mode,
            repo=repo,
            include_code=include_code,
        )
        typer.echo(json.dumps(payload, indent=2))


@app.command("trace")
def trace_query(
    query: str,
    mode: str = typer.Option(default="understand"),
    repo_name: str | None = typer.Option(default=None),
    limit: int = typer.Option(default=12),
    include_code: bool = typer.Option(default=False),
    database_url: str | None = typer.Option(default=None),
) -> None:
    with session_scope(database_url) as session:
        services = build_services(session)
        repo = services["repos"].get_repo_by_name(repo_name) if repo_name else None
        payload = services["retrieval"].retrieve(
            query=query,
            mode=mode,
            repo=repo,
            limit=limit,
            include_code=include_code,
        )
        typer.echo(json.dumps(_trace_summary(payload), indent=2))


@app.command("retrieval-logs")
def retrieval_logs(
    repo_name: str | None = typer.Option(default=None),
    limit: int = typer.Option(default=10),
    database_url: str | None = typer.Option(default=None),
) -> None:
    with session_scope(database_url) as session:
        repo = build_services(session)["repos"].get_repo_by_name(repo_name) if repo_name else None
        query = session.query(RetrievalLog)
        if repo is not None:
            query = query.filter(RetrievalLog.repo_id == repo.id)
        logs = query.order_by(RetrievalLog.created_at.desc()).limit(limit).all()
        typer.echo(
            json.dumps(
                [
                    {
                        "id": log.id,
                        "query": log.query_text,
                        "mode": log.mode,
                        "created_at": log.created_at.isoformat() if log.created_at else None,
                        "packed_files": len(log.packed_context.get("files", [])),
                        "packed_symbols": len(log.packed_context.get("symbols", [])),
                        "packed_memories": len(log.packed_context.get("memories", [])),
                        "stage_counts": (log.diagnostics_json or {}).get("stage_counts", {}),
                    }
                    for log in logs
                ],
                indent=2,
            )
        )


@app.command()
def doctor(database_url: str | None = typer.Option(default=None)) -> None:
    diagnostics = database_diagnostics(database_url)
    typer.echo(json.dumps(diagnostics, indent=2))


@app.command("migrate-postgres-to-sqlite")
def migrate_postgres_to_sqlite(
    target_path: Path = typer.Argument(..., help="SQLite DB file to create"),
    source_database_url: str | None = typer.Option(
        default=None,
        help="Source Postgres URL. Defaults to ARIADNE_DATABASE_URL.",
    ),
    overwrite: bool = typer.Option(default=False, help="Replace target_path if it already exists"),
) -> None:
    source_url = source_database_url or get_settings().database_url
    if source_url.startswith("sqlite"):
        typer.echo("source database must be Postgres; pass --source-database-url explicitly", err=True)
        raise typer.Exit(code=2)

    payload = migrate_to_sqlite(
        source_database_url=source_url,
        target_path=target_path,
        overwrite=overwrite,
    )
    typer.echo(json.dumps(payload, indent=2))


@app.command("reconcile-embeddings")
def reconcile_embeddings(
    target_dimensions: int | None = typer.Option(default=None),
    database_url: str | None = typer.Option(default=None),
) -> None:
    with session_scope(database_url) as session:
        services = build_services(session)
        payload = services["maintenance"].reconcile_embeddings(
            target_dimensions=target_dimensions or get_settings().embedding_dimensions
        )
        typer.echo(json.dumps(payload, indent=2))


@app.command()
def compact(
    keep_retrieval_logs: int = typer.Option(default=100, help="Number of newest retrieval logs to keep"),
    reindex: bool = typer.Option(default=False, help="Reindex repos before pruning orphaned rows"),
    apply: bool = typer.Option(default=False, help="Apply changes. Without this, compact is a dry run"),
    vacuum: bool = typer.Option(default=True, help="Run SQLite VACUUM after applying changes"),
    database_url: str | None = typer.Option(default=None),
) -> None:
    with session_scope(database_url) as session:
        services = build_services(session)
        payload = services["maintenance"].compact_database(
            keep_retrieval_logs=keep_retrieval_logs,
            reindex=reindex,
            dry_run=not apply,
        )

    payload["vacuum"] = {"requested": vacuum, "ran": False}
    if apply and vacuum:
        engine = build_engine(database_url)
        if engine.dialect.name == "sqlite":
            with engine.connect() as connection:
                connection.exec_driver_sql("VACUUM")
            payload["vacuum"]["ran"] = True
        else:
            payload["vacuum"]["skipped"] = "VACUUM is only run automatically for SQLite"

    typer.echo(json.dumps(payload, indent=2))


@memory_app.command("add")
def add_memory(
    title: str,
    content: str,
    memory_type: str = typer.Option(default="decision"),
    repo_name: str | None = typer.Option(default=None),
    summary: str | None = typer.Option(default=None),
    database_url: str | None = typer.Option(default=None),
) -> None:
    with session_scope(database_url) as session:
        services = build_services(session)
        repo = services["repos"].get_repo_by_name(repo_name) if repo_name else None
        memory = services["memory"].create_memory(
            MemoryCreate(
                repo_id=repo.id if repo else None,
                title=title,
                content=content,
                summary=summary,
                memory_type=memory_type,
            )
        )
        typer.echo(json.dumps({"id": memory.id, "title": memory.title}, indent=2))


@memory_app.command("list")
def list_memories(
    repo_name: str | None = typer.Option(default=None),
    database_url: str | None = typer.Option(default=None),
) -> None:
    with session_scope(database_url) as session:
        services = build_services(session)
        repo = services["repos"].get_repo_by_name(repo_name) if repo_name else None
        memories = services["memory"].list_memories(repo.id if repo else None)
        typer.echo(
            json.dumps(
                [
                    {
                        "id": memory.id,
                        "title": memory.title,
                        "type": memory.memory_type.value,
                        "status": memory.status.value,
                    }
                    for memory in memories
                ],
                indent=2,
            )
        )


@memory_app.command("link")
def link_memory(
    memory_id: int,
    to_node_kind: str,
    to_node_id: int,
    edge_type: str = typer.Option(default="APPLIES_TO"),
    database_url: str | None = typer.Option(default=None),
) -> None:
    with session_scope(database_url) as session:
        services = build_services(session)
        edge = services["memory"].link_memory(
            MemoryLinkCreate(
                from_memory_id=memory_id,
                to_node_kind=to_node_kind,
                to_node_id=to_node_id,
                edge_type=edge_type,
            )
        )
        typer.echo(json.dumps({"id": edge.id, "type": edge.edge_type.value}, indent=2))


def _trace_summary(payload: dict) -> dict:
    diagnostics = payload.get("diagnostics", {})
    ranked = diagnostics.get("ranked_candidates", [])
    top_ranked = ranked[:10]
    return {
        "mode": payload.get("mode"),
        "stage_counts": diagnostics.get("stage_counts", {}),
        "top_ranked": top_ranked,
        "packed": {
            "files": [item["path"] for item in payload["context"].get("files", [])],
            "symbols": [item["qualified_name"] for item in payload["context"].get("symbols", [])],
            "memories": [item["title"] for item in payload["context"].get("memories", [])],
        },
    }
