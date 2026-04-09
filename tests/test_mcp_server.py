from __future__ import annotations

from ariadne_index.mcp_server import AriadneMCPServer
from ariadne_index.schemas import RepoCreate
from ariadne_index.bootstrap import build_services


def test_mcp_initialize_and_list_tools(database_url: str) -> None:
    server = AriadneMCPServer(database_url=database_url)

    initialize = server.process_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
        }
    )
    assert initialize is not None
    assert initialize["result"]["protocolVersion"] == "2025-06-18"
    assert initialize["result"]["capabilities"]["tools"]["listChanged"] is False

    listed = server.process_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert listed is not None
    tool_names = {tool["name"] for tool in listed["result"]["tools"]}
    assert {
        "repo_list",
        "repo_add",
        "repo_index",
        "search",
        "retrieve",
        "pack_context",
        "trace",
        "memory_list",
        "memory_add",
    } <= tool_names


def test_mcp_search_and_memory_tool_calls(db_session, sample_repo, initialized_db: str) -> None:
    services = build_services(db_session)
    repo = services["repos"].add_repo(RepoCreate(name="sample", local_path=str(sample_repo)))
    services["indexing"].index_repo(repo)
    db_session.commit()

    server = AriadneMCPServer(database_url=initialized_db)
    server.process_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
        }
    )

    search = server.process_message(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "search", "arguments": {"query": "retry", "repo_name": "sample"}},
        }
    )
    assert search is not None
    assert search["result"]["isError"] is False
    search_payload = search["result"]["structuredContent"]
    assert "app/service.py" in search_payload["files"]
    assert "retry_logic" in search_payload["symbols"]

    memory_add = server.process_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "memory_add",
                "arguments": {
                    "title": "Retry decision",
                    "content": "Retries should stay capped at three attempts.",
                    "memory_type": "decision",
                    "repo_name": "sample",
                },
            },
        }
    )
    assert memory_add is not None
    assert memory_add["result"]["isError"] is False
    memory_id = memory_add["result"]["structuredContent"]["id"]
    assert isinstance(memory_id, int)

    memory_list = server.process_message(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "memory_list", "arguments": {"repo_name": "sample"}},
        }
    )
    assert memory_list is not None
    titles = [item["title"] for item in memory_list["result"]["structuredContent"]["memories"]]
    assert "Retry decision" in titles


def test_mcp_repo_management_tools(sample_repo, initialized_db: str) -> None:
    server = AriadneMCPServer(database_url=initialized_db)
    server.process_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
        }
    )

    repo_add = server.process_message(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "repo_add",
                "arguments": {"name": "sample", "local_path": str(sample_repo)},
            },
        }
    )
    assert repo_add is not None
    assert repo_add["result"]["isError"] is False
    assert repo_add["result"]["structuredContent"]["name"] == "sample"

    repo_list = server.process_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "repo_list", "arguments": {}},
        }
    )
    assert repo_list is not None
    listed_names = [item["name"] for item in repo_list["result"]["structuredContent"]["repos"]]
    assert "sample" in listed_names

    repo_index = server.process_message(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "repo_index", "arguments": {"repo_name": "sample"}},
        }
    )
    assert repo_index is not None
    assert repo_index["result"]["isError"] is False
    payload = repo_index["result"]["structuredContent"]
    assert payload["repo"] == "sample"
    assert payload["discovered"] > 0
