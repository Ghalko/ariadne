from __future__ import annotations

from sqlalchemy.orm import Session

from ariadne_index.config import get_settings
from ariadne_index.db import compatibility_issues_for_engine
from ariadne_index.services.embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
)


def build_embedder() -> EmbeddingProvider:
    settings = get_settings()
    provider = settings.embedding_provider.lower()

    if provider in {"auto", "openai"} and settings.openai_api_key:
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model_name=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )

    if provider == "openai" and not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required when ARIADNE_EMBEDDING_PROVIDER=openai")

    return DeterministicEmbeddingProvider(dimensions=settings.embedding_dimensions)


def build_services(session: Session) -> dict:
    from ariadne_index.services.graph import GraphService
    from ariadne_index.services.indexing import IndexingService
    from ariadne_index.services.maintenance import EmbeddingMaintenanceService
    from ariadne_index.services.memory import MemoryService
    from ariadne_index.services.repository import RepoService
    from ariadne_index.services.retrieval import RetrievalService

    settings = get_settings()
    if settings.strict_db_compatibility:
        issues = compatibility_issues_for_engine(session.get_bind())
        if issues:
            raise ValueError(f"Database compatibility check failed: {'; '.join(issues)}")

    embedder = build_embedder()
    return {
        "repos": RepoService(session),
        "indexing": IndexingService(session, embedder),
        "memory": MemoryService(session, embedder),
        "maintenance": EmbeddingMaintenanceService(session, embedder),
        "retrieval": RetrievalService(session, embedder),
        "graph": GraphService(session),
    }
