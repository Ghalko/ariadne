from __future__ import annotations

from sqlalchemy.orm import Session

from ariadne_index.config import get_settings
from ariadne_index.services.embeddings import DeterministicEmbeddingProvider


def build_embedder() -> DeterministicEmbeddingProvider:
    settings = get_settings()
    return DeterministicEmbeddingProvider(dimensions=settings.embedding_dimensions)


def build_services(session: Session) -> dict:
    from ariadne_index.services.graph import GraphService
    from ariadne_index.services.indexing import IndexingService
    from ariadne_index.services.memory import MemoryService
    from ariadne_index.services.repository import RepoService
    from ariadne_index.services.retrieval import RetrievalService

    embedder = build_embedder()
    return {
        "repos": RepoService(session),
        "indexing": IndexingService(session, embedder),
        "memory": MemoryService(session, embedder),
        "retrieval": RetrievalService(session, embedder),
        "graph": GraphService(session),
    }
