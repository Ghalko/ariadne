from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ariadne_index.bootstrap import build_services
from ariadne_index.config import get_settings
from ariadne_index.db import database_diagnostics, session_scope
from ariadne_index.models.entities import RetrievalLog
from ariadne_index.schemas import MemoryCreate, MemoryLinkCreate, RepoCreate

PROTOCOL_VERSION = "2025-06-18"


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    annotations: dict[str, Any]
    handler: Callable[[dict[str, Any]], dict[str, Any]]


class AriadneMCPServer:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url
        self.settings = get_settings()
        self._initialized = False
        self._tools = {tool.name: tool for tool in self._build_tools()}

    def process_message(self, message: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any] | list[dict[str, Any]] | None:
        if isinstance(message, list):
            responses = [response for item in message if (response := self._process_single(item)) is not None]
            return responses or None
        return self._process_single(message)

    def serve_forever(self) -> None:
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
                response = self.process_message(message)
            except Exception as exc:  # pragma: no cover - stdio loop
                print(f"mcp server error: {exc}", file=sys.stderr)
                response = self._error_response(None, -32603, f"Internal error: {exc}")
            if response is None:
                continue
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()

    def _process_single(self, message: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(message, dict):
            return self._error_response(None, -32600, "Invalid Request")
        if message.get("jsonrpc") != "2.0":
            return self._error_response(message.get("id"), -32600, "Invalid Request")

        method = message.get("method")
        if not isinstance(method, str):
            return self._error_response(message.get("id"), -32600, "Invalid Request")

        request_id = message.get("id")
        params = message.get("params") or {}

        if method == "initialize":
            self._initialized = True
            return self._result_response(
                request_id,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "ariadne", "version": "0.1.0"},
                    "instructions": (
                        "Use Ariadne tools to search code, retrieve compact context, inspect retrieval traces, "
                        "and manage durable repo memories."
                    ),
                },
            )
        if method == "notifications/initialized":
            return None
        if method == "ping":
            return self._result_response(request_id, {})

        if not self._initialized:
            return self._error_response(request_id, -32002, "Server not initialized")

        if method == "tools/list":
            return self._result_response(request_id, {"tools": [self._tool_payload(tool) for tool in self._tools.values()]})

        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if not isinstance(name, str):
                return self._error_response(request_id, -32602, "Tool name is required")
            tool = self._tools.get(name)
            if tool is None:
                return self._error_response(request_id, -32602, f"Unknown tool: {name}")
            try:
                payload = tool.handler(arguments)
            except ValueError as exc:
                return self._result_response(request_id, self._tool_error(str(exc)))
            except Exception as exc:  # pragma: no cover - defensive
                return self._result_response(request_id, self._tool_error(f"{type(exc).__name__}: {exc}"))
            return self._result_response(request_id, self._tool_success(payload))

        return self._error_response(request_id, -32601, f"Method not found: {method}")

    def _build_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="repo_list",
                title="List Repos",
                description="List registered repositories known to Ariadne.",
                input_schema={"type": "object", "additionalProperties": False},
                annotations={"readOnlyHint": True, "idempotentHint": True},
                handler=self._tool_repo_list,
            ),
            ToolDefinition(
                name="repo_add",
                title="Add Repo",
                description="Register a local repository with Ariadne.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "local_path": {"type": "string"},
                    },
                    "required": ["name", "local_path"],
                    "additionalProperties": False,
                },
                annotations={"readOnlyHint": False, "idempotentHint": False},
                handler=self._tool_repo_add,
            ),
            ToolDefinition(
                name="repo_index",
                title="Index Repo",
                description="Index or refresh a registered repository.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "repo_name": {"type": "string"},
                    },
                    "required": ["repo_name"],
                    "additionalProperties": False,
                },
                annotations={"readOnlyHint": False, "idempotentHint": False},
                handler=self._tool_repo_index,
            ),
            ToolDefinition(
                name="search",
                title="Lexical Search",
                description="Run lexical narrowing over files, symbols, and memories.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "repo_name": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                annotations={"readOnlyHint": True, "idempotentHint": True},
                handler=self._tool_search,
            ),
            ToolDefinition(
                name="retrieve",
                title="Hybrid Retrieve",
                description="Run Ariadne hybrid retrieval and return packed context plus scores.",
                input_schema=self._retrieve_schema(),
                annotations={"readOnlyHint": True, "idempotentHint": True},
                handler=self._tool_retrieve,
            ),
            ToolDefinition(
                name="pack_context",
                title="Pack Context",
                description="Return only the packed context payload for a coding task.",
                input_schema=self._retrieve_schema(),
                annotations={"readOnlyHint": True, "idempotentHint": True},
                handler=self._tool_pack_context,
            ),
            ToolDefinition(
                name="trace",
                title="Trace Retrieval",
                description="Inspect stage counts, top-ranked candidates, and packed artifacts for a query.",
                input_schema=self._retrieve_schema(include_code_default=False),
                annotations={"readOnlyHint": True, "idempotentHint": True},
                handler=self._tool_trace,
            ),
            ToolDefinition(
                name="graph",
                title="Traverse Graph",
                description="Traverse Ariadne's explicit graph from a node.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "node_kind": {"type": "string"},
                        "node_id": {"type": "integer", "minimum": 1},
                        "max_hops": {"type": "integer", "minimum": 1},
                        "edge_types": {"type": "array", "items": {"type": "string"}},
                        "limit": {"type": "integer", "minimum": 1},
                    },
                    "required": ["node_kind", "node_id"],
                    "additionalProperties": False,
                },
                annotations={"readOnlyHint": True, "idempotentHint": True},
                handler=self._tool_graph,
            ),
            ToolDefinition(
                name="memory_list",
                title="List Memories",
                description="List durable memories for a repo or globally.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "repo_name": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                annotations={"readOnlyHint": True, "idempotentHint": True},
                handler=self._tool_memory_list,
            ),
            ToolDefinition(
                name="memory_add",
                title="Add Memory",
                description="Create a durable memory node in Ariadne.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "memory_type": {"type": "string"},
                        "repo_name": {"type": "string"},
                        "summary": {"type": "string"},
                    },
                    "required": ["title", "content"],
                    "additionalProperties": False,
                },
                annotations={"readOnlyHint": False, "idempotentHint": False},
                handler=self._tool_memory_add,
            ),
            ToolDefinition(
                name="memory_link",
                title="Link Memory",
                description="Attach a durable memory to a repo graph node.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "memory_id": {"type": "integer", "minimum": 1},
                        "to_node_kind": {"type": "string"},
                        "to_node_id": {"type": "integer", "minimum": 1},
                        "edge_type": {"type": "string"},
                    },
                    "required": ["memory_id", "to_node_kind", "to_node_id"],
                    "additionalProperties": False,
                },
                annotations={"readOnlyHint": False, "idempotentHint": False},
                handler=self._tool_memory_link,
            ),
            ToolDefinition(
                name="retrieval_logs",
                title="Retrieval Logs",
                description="Inspect recent retrieval-log summaries and stage counts.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "repo_name": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1},
                    },
                    "additionalProperties": False,
                },
                annotations={"readOnlyHint": True, "idempotentHint": True},
                handler=self._tool_retrieval_logs,
            ),
            ToolDefinition(
                name="doctor",
                title="Database Doctor",
                description="Check DB schema, pgvector, and embedding compatibility.",
                input_schema={"type": "object", "additionalProperties": False},
                annotations={"readOnlyHint": True, "idempotentHint": True},
                handler=self._tool_doctor,
            ),
        ]

    def _tool_repo_list(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if arguments:
            raise ValueError("repo_list does not take arguments")
        with session_scope(self.database_url) as session:
            services = build_services(session)
            repos = services["repos"].list_repos()
            return {
                "repos": [
                    {
                        "id": repo.id,
                        "name": repo.name,
                        "path": repo.local_path,
                        "branch": repo.active_branch,
                        "commit": repo.current_commit_sha,
                    }
                    for repo in repos
                ]
            }

    def _tool_repo_add(self, arguments: dict[str, Any]) -> dict[str, Any]:
        name = self._require_str(arguments, "name")
        local_path = self._require_str(arguments, "local_path")
        with session_scope(self.database_url) as session:
            services = build_services(session)
            repo = services["repos"].add_repo(RepoCreate(name=name, local_path=local_path))
            return {
                "id": repo.id,
                "name": repo.name,
                "path": repo.local_path,
                "branch": repo.active_branch,
                "commit": repo.current_commit_sha,
            }

    def _tool_repo_index(self, arguments: dict[str, Any]) -> dict[str, Any]:
        repo_name = self._require_str(arguments, "repo_name")
        with session_scope(self.database_url) as session:
            services = build_services(session)
            repo = services["repos"].get_repo_by_name(repo_name)
            return services["indexing"].index_repo(repo)

    def _tool_search(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = self._require_str(arguments, "query")
        repo_name = self._optional_str(arguments, "repo_name")
        limit = self._optional_int(arguments, "limit", default=10)
        with session_scope(self.database_url) as session:
            services = build_services(session)
            repo = services["repos"].get_repo_by_name(repo_name) if repo_name else None
            result = services["retrieval"].lexical.search(query, repo_id=repo.id if repo else None, limit=limit)
            return {
                "files": [file.path for file in result["files"]],
                "symbols": [symbol.qualified_name for symbol in result["symbols"]],
                "memories": [memory.title for memory in result["memories"]],
            }

    def _tool_retrieve(self, arguments: dict[str, Any]) -> dict[str, Any]:
        with session_scope(self.database_url) as session:
            services = build_services(session)
            payload = self._run_retrieve(arguments, services)
            return payload

    def _tool_pack_context(self, arguments: dict[str, Any]) -> dict[str, Any]:
        with session_scope(self.database_url) as session:
            services = build_services(session)
            return self._run_retrieve(arguments, services)["context"]

    def _tool_trace(self, arguments: dict[str, Any]) -> dict[str, Any]:
        with session_scope(self.database_url) as session:
            services = build_services(session)
            payload = self._run_retrieve(arguments, services)
            diagnostics = payload.get("diagnostics", {})
            return {
                "mode": payload.get("mode"),
                "stage_counts": diagnostics.get("stage_counts", {}),
                "top_ranked": diagnostics.get("ranked_candidates", [])[:10],
                "packed": payload.get("context", {}),
            }

    def _tool_graph(self, arguments: dict[str, Any]) -> dict[str, Any]:
        node_kind = self._require_str(arguments, "node_kind")
        node_id = self._require_int(arguments, "node_id")
        max_hops = self._optional_int(arguments, "max_hops", default=1)
        limit = self._optional_int(arguments, "limit", default=20)
        edge_types = arguments.get("edge_types") or []
        if not isinstance(edge_types, list) or not all(isinstance(item, str) for item in edge_types):
            raise ValueError("edge_types must be an array of strings")
        with session_scope(self.database_url) as session:
            services = build_services(session)
            return {
                "results": services["graph"].traverse(
                    start_kind=node_kind,
                    start_id=node_id,
                    max_hops=max_hops,
                    edge_types=edge_types,
                    limit=limit,
                )
            }

    def _tool_memory_list(self, arguments: dict[str, Any]) -> dict[str, Any]:
        repo_name = self._optional_str(arguments, "repo_name")
        with session_scope(self.database_url) as session:
            services = build_services(session)
            repo = services["repos"].get_repo_by_name(repo_name) if repo_name else None
            memories = services["memory"].list_memories(repo.id if repo else None)
            return {
                "memories": [
                    {
                        "id": memory.id,
                        "title": memory.title,
                        "type": memory.memory_type.value,
                        "status": memory.status.value,
                        "summary": memory.summary,
                    }
                    for memory in memories
                ]
            }

    def _tool_memory_add(self, arguments: dict[str, Any]) -> dict[str, Any]:
        title = self._require_str(arguments, "title")
        content = self._require_str(arguments, "content")
        memory_type = self._optional_str(arguments, "memory_type", default="decision")
        repo_name = self._optional_str(arguments, "repo_name")
        summary = self._optional_str(arguments, "summary")
        with session_scope(self.database_url) as session:
            services = build_services(session)
            repo = services["repos"].get_repo_by_name(repo_name) if repo_name else None
            memory = services["memory"].create_memory(
                MemoryCreate(
                    repo_id=repo.id if repo else None,
                    title=title,
                    content=content,
                    summary=summary,
                    memory_type=memory_type,
                )
            )
            return {"id": memory.id, "title": memory.title}

    def _tool_memory_link(self, arguments: dict[str, Any]) -> dict[str, Any]:
        memory_id = self._require_int(arguments, "memory_id")
        to_node_kind = self._require_str(arguments, "to_node_kind")
        to_node_id = self._require_int(arguments, "to_node_id")
        edge_type = self._optional_str(arguments, "edge_type", default="APPLIES_TO")
        with session_scope(self.database_url) as session:
            services = build_services(session)
            edge = services["memory"].link_memory(
                MemoryLinkCreate(
                    from_memory_id=memory_id,
                    to_node_kind=to_node_kind,
                    to_node_id=to_node_id,
                    edge_type=edge_type,
                )
            )
            return {"id": edge.id, "type": edge.edge_type.value}

    def _tool_retrieval_logs(self, arguments: dict[str, Any]) -> dict[str, Any]:
        repo_name = self._optional_str(arguments, "repo_name")
        limit = self._optional_int(arguments, "limit", default=5)
        with session_scope(self.database_url) as session:
            services = build_services(session)
            repo = services["repos"].get_repo_by_name(repo_name) if repo_name else None
            query = session.query(RetrievalLog)
            if repo is not None:
                query = query.filter(RetrievalLog.repo_id == repo.id)
            logs = query.order_by(RetrievalLog.created_at.desc()).limit(limit).all()
            return {
                "logs": [
                    {
                        "id": log.id,
                        "query": log.query_text,
                        "mode": log.mode,
                        "created_at": log.created_at.isoformat() if log.created_at else None,
                        "stage_counts": (log.diagnostics_json or {}).get("stage_counts", {}),
                    }
                    for log in logs
                ]
            }

    def _tool_doctor(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if arguments:
            raise ValueError("doctor does not take arguments")
        return database_diagnostics(self.database_url)

    def _run_retrieve(self, arguments: dict[str, Any], services: dict[str, Any]) -> dict[str, Any]:
        query = self._require_str(arguments, "query")
        mode = self._optional_str(arguments, "mode", default="understand")
        repo_name = self._optional_str(arguments, "repo_name")
        limit = self._optional_int(arguments, "limit", default=12)
        include_code = self._optional_bool(arguments, "include_code", default=True)
        repo = services["repos"].get_repo_by_name(repo_name) if repo_name else None
        return services["retrieval"].retrieve(
            query=query,
            mode=mode,
            repo=repo,
            limit=limit,
            include_code=include_code,
        )

    def _retrieve_schema(self, *, include_code_default: bool = True) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "mode": {"type": "string", "default": "understand"},
                "repo_name": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "default": 12},
                "include_code": {"type": "boolean", "default": include_code_default},
            },
            "required": ["query"],
            "additionalProperties": False,
        }

    def _tool_payload(self, tool: ToolDefinition) -> dict[str, Any]:
        return {
            "name": tool.name,
            "title": tool.title,
            "description": tool.description,
            "inputSchema": tool.input_schema,
            "annotations": tool.annotations,
        }

    def _tool_success(self, payload: dict[str, Any]) -> dict[str, Any]:
        serialized = json.dumps(payload, indent=2, sort_keys=True)
        return {
            "content": [{"type": "text", "text": serialized}],
            "structuredContent": payload,
            "isError": False,
        }

    def _tool_error(self, message: str) -> dict[str, Any]:
        return {
            "content": [{"type": "text", "text": message}],
            "isError": True,
        }

    def _result_response(self, request_id: str | int | None, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _error_response(self, request_id: str | int | None, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    def _require_str(self, arguments: dict[str, Any], name: str) -> str:
        value = arguments.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} is required")
        return value

    def _optional_str(self, arguments: dict[str, Any], name: str, default: str | None = None) -> str | None:
        value = arguments.get(name, default)
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"{name} must be a string")
        return value

    def _require_int(self, arguments: dict[str, Any], name: str) -> int:
        value = arguments.get(name)
        if not isinstance(value, int):
            raise ValueError(f"{name} must be an integer")
        return value

    def _optional_int(self, arguments: dict[str, Any], name: str, default: int) -> int:
        value = arguments.get(name, default)
        if not isinstance(value, int):
            raise ValueError(f"{name} must be an integer")
        return value

    def _optional_bool(self, arguments: dict[str, Any], name: str, default: bool) -> bool:
        value = arguments.get(name, default)
        if not isinstance(value, bool):
            raise ValueError(f"{name} must be a boolean")
        return value


def main() -> None:
    server = AriadneMCPServer()
    server.serve_forever()


if __name__ == "__main__":
    main()
