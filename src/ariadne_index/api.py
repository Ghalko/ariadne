from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from ariadne_index.bootstrap import build_services
from ariadne_index.db import build_session_factory, database_diagnostics, init_database
from ariadne_index.models.entities import RetrievalLog
from ariadne_index.schemas import GraphQuery, MemoryCreate, MemoryLinkCreate, RepoCreate, RetrieveQuery, SearchQuery

app = FastAPI(title="Ariadne", version="0.1.0")


def get_session() -> Generator[Session, None, None]:
    session_factory = build_session_factory()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@app.on_event("startup")
def startup() -> None:
    init_database()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/health/details")
def health_details() -> dict:
    diagnostics = database_diagnostics()
    return {"status": "ok" if not diagnostics["issues"] else "warning", **diagnostics}


@app.post("/repos")
def add_repo(payload: RepoCreate, session: Session = Depends(get_session)) -> dict:
    repo = build_services(session)["repos"].add_repo(payload)
    return {"id": repo.id, "name": repo.name, "path": repo.local_path}


@app.get("/repos")
def list_repos(session: Session = Depends(get_session)) -> list[dict]:
    repos = build_services(session)["repos"].list_repos()
    return [
        {
            "id": repo.id,
            "name": repo.name,
            "path": repo.local_path,
            "branch": repo.active_branch,
            "commit": repo.current_commit_sha,
        }
        for repo in repos
    ]


@app.post("/repos/{repo_name}/index")
def index_repo(repo_name: str, session: Session = Depends(get_session)) -> dict:
    services = build_services(session)
    repo = services["repos"].get_repo_by_name(repo_name)
    return services["indexing"].index_repo(repo)


@app.post("/search")
def search(payload: SearchQuery, session: Session = Depends(get_session)) -> dict:
    services = build_services(session)
    repo = services["repos"].get_repo_by_name(payload.repo_name) if payload.repo_name else None
    result = services["retrieval"].lexical.search(payload.query, repo_id=repo.id if repo else None, limit=payload.limit)
    return {
        "files": [
            {"id": file.id, "path": file.path, "summary": file.summary}
            for file in result["files"]
        ],
        "symbols": [
            {"id": symbol.id, "qualified_name": symbol.qualified_name, "summary": symbol.summary}
            for symbol in result["symbols"]
        ],
        "memories": [
            {"id": memory.id, "title": memory.title, "summary": memory.summary}
            for memory in result["memories"]
        ],
    }


@app.post("/retrieve")
def retrieve(payload: RetrieveQuery, session: Session = Depends(get_session)) -> dict:
    services = build_services(session)
    repo = services["repos"].get_repo_by_name(payload.repo_name) if payload.repo_name else None
    return services["retrieval"].retrieve(
        query=payload.query,
        mode=payload.mode,
        repo=repo,
        limit=payload.limit,
        include_code=payload.include_code,
    )


@app.post("/retrieve/trace")
def retrieve_trace(payload: RetrieveQuery, session: Session = Depends(get_session)) -> dict:
    services = build_services(session)
    repo = services["repos"].get_repo_by_name(payload.repo_name) if payload.repo_name else None
    result = services["retrieval"].retrieve(
        query=payload.query,
        mode=payload.mode,
        repo=repo,
        limit=payload.limit,
        include_code=payload.include_code,
    )
    diagnostics = result.get("diagnostics", {})
    return {
        "mode": result["mode"],
        "stage_counts": diagnostics.get("stage_counts", {}),
        "top_ranked": diagnostics.get("ranked_candidates", [])[:10],
        "packed": result["context"],
    }


@app.post("/pack-context")
def pack_context(payload: RetrieveQuery, session: Session = Depends(get_session)) -> dict:
    services = build_services(session)
    repo = services["repos"].get_repo_by_name(payload.repo_name) if payload.repo_name else None
    return services["retrieval"].retrieve(
        query=payload.query,
        mode=payload.mode,
        repo=repo,
        limit=payload.limit,
        include_code=payload.include_code,
    )["context"]


@app.post("/graph")
def graph(payload: GraphQuery, session: Session = Depends(get_session)) -> list[dict]:
    return build_services(session)["graph"].traverse(
        start_kind=payload.node_kind,
        start_id=payload.node_id,
        max_hops=payload.max_hops,
        edge_types=payload.edge_types,
        limit=payload.limit,
    )


@app.post("/memories")
def create_memory(payload: MemoryCreate, session: Session = Depends(get_session)) -> dict:
    memory = build_services(session)["memory"].create_memory(payload)
    return {"id": memory.id, "title": memory.title}


@app.get("/memories")
def list_memories(repo_id: int | None = None, session: Session = Depends(get_session)) -> list[dict]:
    memories = build_services(session)["memory"].list_memories(repo_id)
    return [
        {
            "id": memory.id,
            "title": memory.title,
            "type": memory.memory_type.value,
            "status": memory.status.value,
            "summary": memory.summary,
        }
        for memory in memories
    ]


@app.post("/memories/link")
def link_memory(payload: MemoryLinkCreate, session: Session = Depends(get_session)) -> dict:
    edge = build_services(session)["memory"].link_memory(payload)
    return {"id": edge.id, "type": edge.edge_type.value}


@app.get("/retrieval-logs")
def retrieval_logs(
    repo_name: str | None = None,
    limit: int = 10,
    session: Session = Depends(get_session),
) -> list[dict]:
    repo = build_services(session)["repos"].get_repo_by_name(repo_name) if repo_name else None
    query = session.query(RetrievalLog)
    if repo is not None:
        query = query.filter(RetrievalLog.repo_id == repo.id)
    logs = query.order_by(RetrievalLog.created_at.desc()).limit(limit).all()
    return [
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
    ]
