from __future__ import annotations

from sqlalchemy.orm import Session

from ariadne_index.models.entities import Embedding
from ariadne_index.services.embeddings import DeterministicEmbeddingProvider


def upsert_embedding(
    session: Session,
    *,
    repo_id: int | None,
    node_kind: str,
    node_id: int,
    embedding_role: str,
    content: str,
    embedder: DeterministicEmbeddingProvider,
) -> Embedding:
    vector = embedder.embed(content)
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
            repo_id=repo_id,
            node_kind=node_kind,
            node_id=node_id,
            embedding_role=embedding_role,
            model_name=embedder.model_name,
            dimensions=embedder.dimensions,
            vector=vector,
            content_preview=content[:250],
        )
        session.add(embedding)
    else:
        embedding.repo_id = repo_id
        embedding.model_name = embedder.model_name
        embedding.dimensions = embedder.dimensions
        embedding.vector = vector
        embedding.content_preview = content[:250]
    session.flush()
    return embedding
