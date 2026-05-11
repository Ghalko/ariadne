from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from ariadne_index.models.entities import Edge, Embedding, FileRecord, Memory, Repo, RetrievalLog, SymbolRecord
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

    def compact_database(
        self,
        *,
        keep_retrieval_logs: int = 100,
        reindex: bool = False,
        dry_run: bool = True,
    ) -> dict:
        if keep_retrieval_logs < 0:
            raise ValueError("keep_retrieval_logs must be >= 0")

        before = self._table_counts()
        repo_results = []
        if reindex and not dry_run:
            for repo in self.session.query(Repo).order_by(Repo.name):
                repo_results.append(self.indexing.index_repo(repo))

        stale_log_ids = self._stale_retrieval_log_ids(keep_retrieval_logs)
        orphan_embedding_ids = self._orphan_embedding_ids()
        orphan_edge_ids = self._orphan_edge_ids()

        if not dry_run:
            if stale_log_ids:
                self.session.query(RetrievalLog).filter(RetrievalLog.id.in_(stale_log_ids)).delete(
                    synchronize_session=False
                )
            if orphan_edge_ids:
                self.session.query(Edge).filter(Edge.id.in_(orphan_edge_ids)).delete(synchronize_session=False)
            if orphan_embedding_ids:
                self.session.query(Embedding).filter(Embedding.id.in_(orphan_embedding_ids)).delete(
                    synchronize_session=False
                )
            self.session.flush()

        after = self._table_counts() if not dry_run else before
        return {
            "dry_run": dry_run,
            "reindex_requested": reindex,
            "repo_results": repo_results,
            "keep_retrieval_logs": keep_retrieval_logs,
            "before": before,
            "after": after,
            "would_delete": {
                "retrieval_logs": len(stale_log_ids),
                "orphan_edges": len(orphan_edge_ids),
                "orphan_embeddings": len(orphan_embedding_ids),
            },
            "deleted": {
                "retrieval_logs": 0 if dry_run else len(stale_log_ids),
                "orphan_edges": 0 if dry_run else len(orphan_edge_ids),
                "orphan_embeddings": 0 if dry_run else len(orphan_embedding_ids),
            },
        }

    def _table_counts(self) -> dict[str, int]:
        return {
            "repos": self.session.query(Repo).count(),
            "files": self.session.query(FileRecord).count(),
            "symbols": self.session.query(SymbolRecord).count(),
            "memories": self.session.query(Memory).count(),
            "edges": self.session.query(Edge).count(),
            "embeddings": self.session.query(Embedding).count(),
            "retrieval_logs": self.session.query(RetrievalLog).count(),
        }

    def _stale_retrieval_log_ids(self, keep_retrieval_logs: int) -> list[int]:
        retained_ids = {
            log_id
            for (log_id,) in (
                self.session.query(RetrievalLog.id)
                .order_by(RetrievalLog.created_at.desc(), RetrievalLog.id.desc())
                .limit(keep_retrieval_logs)
                .all()
            )
        }
        query = self.session.query(RetrievalLog.id)
        if retained_ids:
            query = query.filter(~RetrievalLog.id.in_(retained_ids))
        return [log_id for (log_id,) in query.all()]

    def _orphan_embedding_ids(self) -> list[int]:
        existing = self._existing_node_ids()
        orphan_ids: list[int] = []
        for embedding in self.session.query(Embedding.id, Embedding.node_kind, Embedding.node_id):
            if embedding.node_id not in existing.get(embedding.node_kind, set()):
                orphan_ids.append(embedding.id)
        return orphan_ids

    def _orphan_edge_ids(self) -> list[int]:
        existing = self._existing_node_ids()
        orphan_ids: list[int] = []
        for edge in self.session.query(
            Edge.id,
            Edge.from_node_kind,
            Edge.from_node_id,
            Edge.to_node_kind,
            Edge.to_node_id,
        ):
            from_exists = edge.from_node_id in existing.get(edge.from_node_kind, set())
            to_exists = edge.to_node_id in existing.get(edge.to_node_kind, set())
            if not from_exists or not to_exists:
                orphan_ids.append(edge.id)
        return orphan_ids

    def _existing_node_ids(self) -> dict[str, set[int]]:
        return {
            "repo": {id_ for (id_,) in self.session.query(Repo.id).all()},
            "file": {id_ for (id_,) in self.session.query(FileRecord.id).all()},
            "symbol": {id_ for (id_,) in self.session.query(SymbolRecord.id).all()},
            "memory": {id_ for (id_,) in self.session.query(Memory.id).all()},
        }
