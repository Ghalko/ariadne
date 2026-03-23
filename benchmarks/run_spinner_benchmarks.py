from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


BENCHMARK_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BENCHMARK_ROOT.parent
SPINNER_ROOT = PROJECT_ROOT / "spinner"
QUERIES_PATH = BENCHMARK_ROOT / "queries.json"


@dataclass(slots=True)
class QueryResult:
    query_id: str
    mode: str
    query: str
    expected_file_count: int
    expected_symbol_count: int
    expected_test_count: int
    expected_doc_count: int
    expected_memory_count: int
    file_hits: list[str]
    symbol_hits: list[str]
    test_hits: list[str]
    doc_hits: list[str]
    memory_hits: list[str]
    retrieved_files: list[str]
    retrieved_symbols: list[str]
    retrieved_memories: list[str]
    estimated_tokens: int
    max_context_items: int

    @property
    def artifact_recall(self) -> float:
        hits = len(self.file_hits) + len(self.symbol_hits) + len(self.test_hits) + len(self.doc_hits) + len(self.memory_hits)
        total = (
            self.expected_file_count
            + self.expected_symbol_count
            + self.expected_test_count
            + self.expected_doc_count
            + self.expected_memory_count
        )
        return 1.0 if total == 0 else hits / total


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Ariadne retrieval benchmarks against Spinner.")
    parser.add_argument("--queries", default=str(QUERIES_PATH), help="Path to benchmark queries JSON.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    parser.add_argument("--limit", type=int, default=None, help="Optional global limit override.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_benchmarks(Path(args.queries), limit_override=args.limit)
    if args.json:
        print(json.dumps(payload, indent=2))
        return
    print(render_report(payload))


def run_benchmarks(queries_path: Path, *, limit_override: int | None = None) -> dict[str, Any]:
    os.environ["ARIADNE_EMBEDDING_PROVIDER"] = "deterministic"
    os.environ.pop("OPENAI_API_KEY", None)

    from ariadne_index.config import get_settings
    from ariadne_index.db import init_database, session_scope
    from ariadne_index.schemas import MemoryCreate, RepoCreate
    from ariadne_index.services.embeddings import DeterministicEmbeddingProvider
    from ariadne_index.services.indexing import IndexingService
    from ariadne_index.services.memory import MemoryService
    from ariadne_index.services.repository import RepoService
    from ariadne_index.services.retrieval import RetrievalService

    get_settings.cache_clear()
    queries = json.loads(queries_path.read_text())

    with tempfile.TemporaryDirectory(prefix="ariadne-bench-") as temp_dir:
        database_url = f"sqlite+pysqlite:///{Path(temp_dir) / 'bench.db'}"
        init_database(database_url)
        with session_scope(database_url) as session:
            embedder = DeterministicEmbeddingProvider(dimensions=get_settings().embedding_dimensions)
            repos = RepoService(session)
            indexing = IndexingService(session, embedder)
            memory = MemoryService(session, embedder)
            retrieval = RetrievalService(session, embedder)

            repo = repos.add_repo(RepoCreate(name="spinner", local_path=str(SPINNER_ROOT)))
            indexing.index_repo(repo)
            seed_doc_memories(repo.id, memory, MemoryCreate=MemoryCreate)

            results = [
                evaluate_query(
                    query=query,
                    retrieval=retrieval,
                    repo=repo,
                    limit_override=limit_override,
                )
                for query in queries
            ]

    return {
        "summary": summarize(results, total_queries=len(queries)),
        "results": [asdict(result) for result in results],
    }


def seed_doc_memories(repo_id: int, memory_service, *, MemoryCreate) -> None:
    docs = sorted((SPINNER_ROOT / "docs").rglob("*.md"))
    for doc_path in docs:
        relative = doc_path.relative_to(SPINNER_ROOT).as_posix()
        content = doc_path.read_text(encoding="utf-8")
        title = next((line.strip("# ").strip() for line in content.splitlines() if line.startswith("#")), doc_path.stem)
        summary = next((line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")), title)
        memory_type = infer_memory_type(relative)
        memory_service.create_memory(
            MemoryCreate(
                repo_id=repo_id,
                title=title,
                content=content,
                summary=summary,
                memory_type=memory_type,
                metadata_json={"source_path": relative},
            )
        )


def infer_memory_type(relative_path: str) -> str:
    if "/adr/" in relative_path:
        return "decision"
    if "/runbooks/" in relative_path:
        return "runbook_note"
    return "design_note"


def evaluate_query(*, query: dict[str, Any], retrieval, repo, limit_override: int | None) -> QueryResult:
    limit = limit_override or query["max_context_items"]
    payload = retrieval.retrieve(
        query=query["query"],
        mode=query["mode"],
        repo=repo,
        limit=limit,
        include_code=False,
    )
    context = payload["context"]
    retrieved_files = [item["path"] for item in context["files"]]
    retrieved_symbols = [item["qualified_name"] for item in context["symbols"]]
    retrieved_memories = [item["title"] for item in context["memories"]]

    file_hits = intersect(query["gold_files"], retrieved_files)
    test_hits = intersect(query["gold_tests"], retrieved_files)
    doc_hits = intersect(query["gold_docs"], retrieved_files)
    memory_hits = intersect(query["gold_memories"], retrieved_memories)
    symbol_hits = match_symbols(query["gold_symbols"], retrieved_symbols)

    estimated_tokens = sum(len(item["summary"].split()) for item in context["files"] if item.get("summary")) + sum(
        len(item["summary"].split()) for item in context["memories"] if item.get("summary")
    )

    return QueryResult(
        query_id=query["id"],
        mode=query["mode"],
        query=query["query"],
        expected_file_count=len(query["gold_files"]),
        expected_symbol_count=len(query["gold_symbols"]),
        expected_test_count=len(query["gold_tests"]),
        expected_doc_count=len(query["gold_docs"]),
        expected_memory_count=len(query["gold_memories"]),
        file_hits=file_hits,
        symbol_hits=symbol_hits,
        test_hits=test_hits,
        doc_hits=doc_hits,
        memory_hits=memory_hits,
        retrieved_files=retrieved_files,
        retrieved_symbols=retrieved_symbols,
        retrieved_memories=retrieved_memories,
        estimated_tokens=estimated_tokens,
        max_context_items=query["max_context_items"],
    )


def intersect(expected: list[str], actual: list[str]) -> list[str]:
    actual_set = set(actual)
    return [item for item in expected if item in actual_set]


def match_symbols(expected: list[str], actual: list[str]) -> list[str]:
    hits: list[str] = []
    for symbol in expected:
        if any(candidate == symbol or candidate.endswith(f".{symbol}") for candidate in actual):
            hits.append(symbol)
    return hits


def summarize(results: list[QueryResult], *, total_queries: int) -> dict[str, Any]:
    def hit_rate(expected_attr: str, hits_attr: str):
        eligible_results = [result for result in results if getattr(result, expected_attr) > 0]
        if not eligible_results:
            return None
        hits = sum(1 for result in eligible_results if len(getattr(result, hits_attr)) > 0)
        return round(hits / len(eligible_results), 3)

    return {
        "queries": total_queries,
        "file_hit_rate": hit_rate("expected_file_count", "file_hits"),
        "symbol_hit_rate": hit_rate("expected_symbol_count", "symbol_hits"),
        "test_hit_rate": hit_rate("expected_test_count", "test_hits"),
        "doc_hit_rate": hit_rate("expected_doc_count", "doc_hits"),
        "memory_hit_rate": hit_rate("expected_memory_count", "memory_hits"),
        "avg_artifact_recall": round(sum(result.artifact_recall for result in results) / total_queries, 3),
        "avg_retrieved_files": round(sum(len(result.retrieved_files) for result in results) / total_queries, 2),
        "avg_retrieved_symbols": round(sum(len(result.retrieved_symbols) for result in results) / total_queries, 2),
        "avg_retrieved_memories": round(sum(len(result.retrieved_memories) for result in results) / total_queries, 2),
    }


def render_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "Spinner benchmark results",
        f"queries: {summary['queries']}",
        f"file hit rate: {summary['file_hit_rate']}",
        f"symbol hit rate: {summary['symbol_hit_rate']}",
        f"test hit rate: {summary['test_hit_rate']}",
        f"doc hit rate: {summary['doc_hit_rate']}",
        f"memory hit rate: {summary['memory_hit_rate']}",
        f"avg artifact recall: {summary['avg_artifact_recall']}",
        f"avg retrieved files: {summary['avg_retrieved_files']}",
        f"avg retrieved symbols: {summary['avg_retrieved_symbols']}",
        f"avg retrieved memories: {summary['avg_retrieved_memories']}",
        "",
        "Per-query snapshot:",
    ]
    for result in payload["results"]:
        lines.append(
            f"- {result['query_id']}: "
            f"files={len(result['file_hits'])}, "
            f"symbols={len(result['symbol_hits'])}, "
            f"tests={len(result['test_hits'])}, "
            f"docs={len(result['doc_hits'])}, "
            f"memories={len(result['memory_hits'])}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
