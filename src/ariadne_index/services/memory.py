from __future__ import annotations

from sqlalchemy.orm import Session

from ariadne_index.models.entities import Memory
from ariadne_index.models.enums import EdgeType
from ariadne_index.schemas import MemoryCreate, MemoryLinkCreate
from ariadne_index.services.embeddings import EmbeddingProvider
from ariadne_index.services.graph import GraphService
from ariadne_index.services.secrets import redact_secret_values
from ariadne_index.services.storage import upsert_embedding


class MemoryService:
    def __init__(self, session: Session, embedder: EmbeddingProvider) -> None:
        self.session = session
        self.embedder = embedder
        self.graph = GraphService(session)

    def create_memory(self, payload: MemoryCreate) -> Memory:
        memory = Memory(**redact_secret_values(payload.model_dump()))
        self.session.add(memory)
        self.session.flush()
        upsert_embedding(
            self.session,
            repo_id=memory.repo_id,
            node_kind="memory",
            node_id=memory.id,
            embedding_role="summary",
            content=memory.summary or memory.content,
            embedder=self.embedder,
        )
        return memory

    def link_memory(self, payload: MemoryLinkCreate):
        edge_type = payload.edge_type or EdgeType.applies_to
        memory = self.session.get(Memory, payload.from_memory_id)
        return self.graph.add_edge(
            repo_id=memory.repo_id if memory else None,
            from_node_kind="memory",
            from_node_id=payload.from_memory_id,
            to_node_kind=payload.to_node_kind,
            to_node_id=payload.to_node_id,
            edge_type=edge_type,
            metadata_json=payload.metadata_json,
        )

    def list_memories(self, repo_id: int | None = None) -> list[Memory]:
        query = self.session.query(Memory)
        if repo_id is not None:
            query = query.filter(Memory.repo_id == repo_id)
        return list(query.order_by(Memory.updated_at.desc()))
