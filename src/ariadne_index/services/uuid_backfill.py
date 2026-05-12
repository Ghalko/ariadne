from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from ariadne_index.models.entities import Edge, Embedding, FileRecord, Memory, Repo, RetrievalLog, SymbolRecord
from ariadne_index.services.identity import edge_uuid, embedding_uuid, file_uuid, random_uuid, repo_uuid, symbol_uuid


UUID_COLUMNS = {
    "repos": ["uuid"],
    "files": ["uuid"],
    "symbols": ["uuid"],
    "memories": ["uuid"],
    "edges": ["uuid", "from_node_uuid", "to_node_uuid"],
    "embeddings": ["uuid", "node_uuid"],
    "retrieval_logs": ["uuid"],
}


def ensure_uuid_columns(session: Session) -> list[str]:
    engine = session.get_bind()
    inspector = inspect(engine)
    added: list[str] = []
    for table_name, columns in UUID_COLUMNS.items():
        existing = {column["name"] for column in inspector.get_columns(table_name)}
        for column in columns:
            if column in existing:
                continue
            session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column} VARCHAR(36)"))
            added.append(f"{table_name}.{column}")
    session.flush()
    return added


def backfill_uuids(session: Session) -> dict:
    ensure_uuid_columns(session)
    counts = {table_name: 0 for table_name in UUID_COLUMNS}

    for repo in session.query(Repo).order_by(Repo.id):
        if not repo.uuid:
            repo.uuid = repo_uuid(repo.name)
            counts["repos"] += 1
    session.flush()

    for file_record in session.query(FileRecord).order_by(FileRecord.id):
        repo = session.get(Repo, file_record.repo_id)
        if not file_record.uuid:
            file_record.uuid = file_uuid(repo.uuid if repo and repo.uuid else str(file_record.repo_id), file_record.path)
            counts["files"] += 1
    session.flush()

    for symbol in session.query(SymbolRecord).order_by(SymbolRecord.id):
        file_record = session.get(FileRecord, symbol.file_id)
        if not symbol.uuid:
            symbol.uuid = symbol_uuid(
                file_record.uuid if file_record and file_record.uuid else str(symbol.file_id),
                symbol.qualified_name,
                symbol.name,
                symbol.line_start,
                symbol.line_end,
            )
            counts["symbols"] += 1
    session.flush()

    for memory in session.query(Memory).order_by(Memory.id):
        if not memory.uuid:
            memory.uuid = random_uuid()
            counts["memories"] += 1
    session.flush()

    for edge in session.query(Edge).order_by(Edge.id):
        if not edge.from_node_uuid:
            edge.from_node_uuid = _node_uuid(session, edge.from_node_kind, edge.from_node_id)
        if not edge.to_node_uuid:
            edge.to_node_uuid = _node_uuid(session, edge.to_node_kind, edge.to_node_id)
        if not edge.uuid and edge.from_node_uuid and edge.to_node_uuid:
            repo = session.get(Repo, edge.repo_id) if edge.repo_id is not None else None
            edge.uuid = edge_uuid(repo.uuid if repo else None, edge.from_node_uuid, edge.to_node_uuid, edge.edge_type.value, edge.metadata_json)
            counts["edges"] += 1
    session.flush()

    for embedding in session.query(Embedding).order_by(Embedding.id):
        if not embedding.node_uuid:
            embedding.node_uuid = _node_uuid(session, embedding.node_kind, embedding.node_id)
        if not embedding.uuid and embedding.node_uuid:
            embedding.uuid = embedding_uuid(embedding.node_uuid, embedding.embedding_role, embedding.model_name, embedding.dimensions)
            counts["embeddings"] += 1
    session.flush()

    for log in session.query(RetrievalLog).order_by(RetrievalLog.id):
        if not log.uuid:
            log.uuid = random_uuid()
            counts["retrieval_logs"] += 1
    session.flush()
    return counts


def _node_uuid(session: Session, node_kind: str, node_id: int) -> str | None:
    model = {
        "repo": Repo,
        "file": FileRecord,
        "symbol": SymbolRecord,
        "memory": Memory,
    }.get(node_kind)
    if model is None:
        return None
    node = session.get(model, node_id)
    return node.uuid if node else None
