from __future__ import annotations

from collections import deque

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ariadne_index.models.entities import Edge, FileRecord, Memory, Repo, SymbolRecord
from ariadne_index.models.enums import EdgeType
from ariadne_index.services.identity import edge_uuid


class GraphService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_edge(
        self,
        *,
        repo_id: int | None,
        from_node_kind: str,
        from_node_id: int,
        to_node_kind: str,
        to_node_id: int,
        edge_type: EdgeType,
        metadata_json: dict | None = None,
        weight: float = 1.0,
    ) -> Edge:
        from_uuid = self._node_uuid(from_node_kind, from_node_id)
        to_uuid = self._node_uuid(to_node_kind, to_node_id)
        repo_uuid = self._repo_uuid(repo_id)
        edge = Edge(
            uuid=edge_uuid(repo_uuid, from_uuid or str(from_node_id), to_uuid or str(to_node_id), edge_type.value, metadata_json or {}),
            repo_id=repo_id,
            from_node_kind=from_node_kind,
            from_node_id=from_node_id,
            from_node_uuid=from_uuid,
            to_node_kind=to_node_kind,
            to_node_id=to_node_id,
            to_node_uuid=to_uuid,
            edge_type=edge_type,
            metadata_json=metadata_json or {},
            weight=weight,
        )
        self.session.add(edge)
        self.session.flush()
        return edge

    def _repo_uuid(self, repo_id: int | None) -> str | None:
        if repo_id is None:
            return None
        repo = self.session.get(Repo, repo_id)
        return repo.uuid if repo else None

    def _node_uuid(self, node_kind: str, node_id: int) -> str | None:
        model = {
            "repo": Repo,
            "file": FileRecord,
            "symbol": SymbolRecord,
            "memory": Memory,
        }.get(node_kind)
        if model is None:
            return None
        node = self.session.get(model, node_id)
        return node.uuid if node else None

    def neighbors(
        self,
        *,
        node_kind: str,
        node_id: int,
        edge_types: list[EdgeType] | None = None,
        limit: int = 20,
    ) -> list[Edge]:
        query = self.session.query(Edge).filter(
            or_(
                (Edge.from_node_kind == node_kind) & (Edge.from_node_id == node_id),
                (Edge.to_node_kind == node_kind) & (Edge.to_node_id == node_id),
            )
        )
        if edge_types:
            query = query.filter(Edge.edge_type.in_(edge_types))
        return list(query.limit(limit))

    def traverse(
        self,
        *,
        start_kind: str,
        start_id: int,
        max_hops: int = 1,
        edge_types: list[EdgeType] | None = None,
        limit: int = 20,
    ) -> list[dict]:
        queue = deque([(start_kind, start_id, 0, [])])
        visited = {(start_kind, start_id)}
        results: list[dict] = []

        while queue and len(results) < limit:
            node_kind, node_id, hops, path = queue.popleft()
            if hops >= max_hops:
                continue
            for edge in self.neighbors(node_kind=node_kind, node_id=node_id, edge_types=edge_types, limit=limit):
                if edge.from_node_kind == node_kind and edge.from_node_id == node_id:
                    target_kind, target_id = edge.to_node_kind, edge.to_node_id
                else:
                    target_kind, target_id = edge.from_node_kind, edge.from_node_id
                target = (target_kind, target_id)
                if target in visited:
                    continue
                visited.add(target)
                edge_path = [*path, edge.edge_type.value]
                results.append(
                    {
                        "node_kind": target_kind,
                        "node_id": target_id,
                        "path": edge_path,
                        "hops": hops + 1,
                    }
                )
                queue.append((target_kind, target_id, hops + 1, edge_path))
        return results
