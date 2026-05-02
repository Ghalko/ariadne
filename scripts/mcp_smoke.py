from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from ariadne_index.mcp_server import AriadneMCPServer


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke check the Ariadne MCP server against the live DB.")
    parser.add_argument("--repo", default="ariadne", help="Registered repo name to index and verify.")
    parser.add_argument(
        "--query",
        default="where is the Ariadne MCP server and dogfooding workflow documented",
        help="Query used for the pack_context smoke call.",
    )
    args = parser.parse_args()

    server = AriadneMCPServer()
    request_id = 1

    def send(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        nonlocal request_id
        response = server.process_message(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params or {},
            }
        )
        request_id += 1
        if response is None:
            raise RuntimeError(f"no response for {method}")
        if "error" in response:
            raise RuntimeError(json.dumps(response["error"], sort_keys=True))
        return response["result"]

    def call_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        result = send("tools/call", {"name": name, "arguments": arguments or {}})
        if result.get("isError"):
            raise RuntimeError(result["content"][0]["text"])
        return result["structuredContent"]

    send(
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "ariadne-mcp-smoke", "version": "1"},
        },
    )

    tools = send("tools/list")["tools"]
    tool_names = {tool["name"] for tool in tools}
    required_tools = {"doctor", "repo_list", "repo_index", "pack_context", "memory_list"}
    missing_tools = sorted(required_tools - tool_names)
    if missing_tools:
        raise RuntimeError(f"missing MCP tools: {', '.join(missing_tools)}")

    doctor = call_tool("doctor")
    if doctor.get("issues"):
        raise RuntimeError(f"doctor reported issues: {doctor['issues']}")

    index_result = call_tool("repo_index", {"repo_name": args.repo})
    repos = call_tool("repo_list")["repos"]
    repo = next((item for item in repos if item["name"] == args.repo), None)
    if repo is None:
        raise RuntimeError(f"repo not found after repo_index: {args.repo}")

    expected_commit = _git_commit(Path(repo["path"]))
    if expected_commit and repo.get("commit") != expected_commit:
        raise RuntimeError(
            f"repo commit mismatch for {args.repo}: got {repo.get('commit')}, expected {expected_commit}"
        )

    packed = call_tool(
        "pack_context",
        {
            "repo_name": args.repo,
            "query": args.query,
            "mode": "docs",
            "limit": 8,
            "include_code": False,
        },
    )
    if not packed.get("files") and not packed.get("symbols") and not packed.get("memories"):
        raise RuntimeError("pack_context returned no files, symbols, or memories")

    summary = {
        "status": "ok",
        "repo": args.repo,
        "commit": repo.get("commit"),
        "indexed": index_result.get("indexed"),
        "skipped": index_result.get("skipped"),
        "discovered": index_result.get("discovered"),
        "tools": sorted(required_tools),
        "packed_files": [item["path"] for item in packed.get("files", [])],
        "packed_symbols": [item["qualified_name"] for item in packed.get("symbols", [])],
        "packed_memories": [item["title"] for item in packed.get("memories", [])],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _git_commit(path: Path) -> str | None:
    if not (path / ".git").exists():
        return None
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"mcp smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
