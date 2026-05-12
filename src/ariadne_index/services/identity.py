from __future__ import annotations

import json
import uuid
from typing import Any


ARIADNE_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "ariadne-index")


def random_uuid() -> str:
    return str(uuid.uuid4())


def stable_uuid(*parts: Any) -> str:
    normalized = json.dumps([_normalize(part) for part in parts], sort_keys=True, default=str)
    return str(uuid.uuid5(ARIADNE_NAMESPACE, normalized))


def repo_uuid(name: str) -> str:
    return stable_uuid("repo", name)


def file_uuid(repo_public_id: str, path: str) -> str:
    return stable_uuid("file", repo_public_id, path)


def symbol_uuid(file_public_id: str, qualified_name: str | None, name: str, line_start: int, line_end: int) -> str:
    return stable_uuid("symbol", file_public_id, qualified_name or name, line_start, line_end)


def edge_uuid(
    repo_public_id: str | None,
    from_node_uuid: str,
    to_node_uuid: str,
    edge_type: str,
    metadata_json: dict | None,
) -> str:
    return stable_uuid("edge", repo_public_id, from_node_uuid, to_node_uuid, edge_type, metadata_json or {})


def embedding_uuid(node_uuid: str, embedding_role: str, model_name: str, dimensions: int) -> str:
    return stable_uuid("embedding", node_uuid, embedding_role, model_name, dimensions)


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value
