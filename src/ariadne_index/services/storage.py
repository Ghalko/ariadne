from __future__ import annotations

from sqlalchemy.orm import Session

from ariadne_index.models.entities import Embedding, FileRecord, Memory, Repo, SymbolRecord
from ariadne_index.services.embeddings import EmbeddingProvider
from ariadne_index.services.identity import embedding_uuid
from ariadne_index.services.secrets import redact_secrets


def upsert_embedding(
    session: Session,
    *,
    repo_id: int | None,
    node_kind: str,
    node_id: int,
    embedding_role: str,
    content: str,
    embedder: EmbeddingProvider,
) -> Embedding:
    safe_content = redact_secrets(content) or ""
    vector = embedder.embed(safe_content)
    node_public_id = _node_uuid(session, node_kind, node_id)
    embedding = (
        session.query(Embedding)
        .filter(
            Embedding.node_kind == node_kind,
            Embedding.node_id == node_id,
            Embedding.embedding_role == embedding_role,
        )
        .one_or_none()
    )
    if embedding is None:
        embedding = Embedding(
            uuid=embedding_uuid(node_public_id or f"{node_kind}:{node_id}", embedding_role, embedder.model_name, embedder.dimensions),
            repo_id=repo_id,
            node_kind=node_kind,
            node_id=node_id,
            node_uuid=node_public_id,
            embedding_role=embedding_role,
            model_name=embedder.model_name,
            dimensions=embedder.dimensions,
            vector=vector,
            content_preview=safe_content[:250],
        )
        session.add(embedding)
    else:
        embedding.repo_id = repo_id
        embedding.node_uuid = node_public_id
        if not embedding.uuid:
            embedding.uuid = embedding_uuid(node_public_id or f"{node_kind}:{node_id}", embedding_role, embedder.model_name, embedder.dimensions)
        embedding.model_name = embedder.model_name
        embedding.dimensions = embedder.dimensions
        embedding.vector = vector
        embedding.content_preview = safe_content[:250]
    session.flush()
    return embedding


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
