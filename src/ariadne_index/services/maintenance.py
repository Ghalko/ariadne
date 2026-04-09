from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from ariadne_index.models.entities import Embedding, Memory, Repo
from ariadne_index.services.embeddings import EmbeddingProvider
from ariadne_index.services.indexing import IndexingService
from ariadne_index.services.storage import upsert_embedding


class EmbeddingMaintenanceService:
    def __init__(self, session: Session, embedder: EmbeddingProvider) -> None:
        self.session = session
        self.embedder = embedder
        self.indexing = IndexingService(session, embedder)

    def reconcile_embeddings(self, *, target_dimensions: int) -> dict:
        engine = self.session.get_bind()
        dialect = engine.dialect.name
        existing_count = self.session.query(Embedding).count()

        if dialect == "postgresql":
            self.session.execute(text("DROP INDEX IF EXISTS ix_embeddings_vector_hnsw"))
        self.session.query(Embedding).delete()
        self.session.flush()

        if dialect == "postgresql":
            self.session.execute(
                text(f"ALTER TABLE embeddings ALTER COLUMN vector TYPE vector({int(target_dimensions)})")
            )
            self.session.execute(
                text(
                    "CREATE INDEX ix_embeddings_vector_hnsw "
                    "ON embeddings USING hnsw (vector vector_cosine_ops) "
                    "WITH (m = 16, ef_construction = 64)"
                )
            )

        repos = list(self.session.query(Repo).order_by(Repo.name))
        repo_results = []
        for repo in repos:
            result = self.indexing.index_repo(repo)
            repo_results.append(result)

        memory_count = 0
        for memory in self.session.query(Memory).order_by(Memory.id):
            upsert_embedding(
                self.session,
                repo_id=memory.repo_id,
                node_kind="memory",
                node_id=memory.id,
                embedding_role="summary",
                content=memory.summary or memory.content,
                embedder=self.embedder,
            )
            memory_count += 1

        rebuilt_count = self.session.query(Embedding).count()
        return {
            "target_dimensions": target_dimensions,
            "dialect": dialect,
            "cleared_embeddings": existing_count,
            "repos_reindexed": len(repos),
            "repo_results": repo_results,
            "memory_embeddings_rebuilt": memory_count,
            "final_embedding_count": rebuilt_count,
        }
