from __future__ import annotations

from ariadne_index.bootstrap import build_services
from ariadne_index.models.entities import Edge, RetrievalLog
from ariadne_index.models.enums import EdgeType
from ariadne_index.schemas import MemoryCreate, MemoryLinkCreate, RepoCreate


def test_index_repo_extracts_files_and_symbols(db_session, sample_repo) -> None:
    services = build_services(db_session)
    repo = services["repos"].add_repo(RepoCreate(name="sample", local_path=str(sample_repo)))
    result = services["indexing"].index_repo(repo)

    assert result["discovered"] == 6
    assert result["indexed"] == 6

    search = services["retrieval"].lexical.search("retry", repo_id=repo.id)
    assert any(file.path == "app/service.py" for file in search["files"])
    assert any(symbol.qualified_name == "retry_logic" for symbol in search["symbols"])


def test_retrieve_includes_memory_context(db_session, sample_repo) -> None:
    services = build_services(db_session)
    repo = services["repos"].add_repo(RepoCreate(name="sample", local_path=str(sample_repo)))
    services["indexing"].index_repo(repo)

    search = services["retrieval"].lexical.search("retry_logic", repo_id=repo.id)
    symbol = next(symbol for symbol in search["symbols"] if symbol.qualified_name == "retry_logic")

    memory = services["memory"].create_memory(
        MemoryCreate(
            repo_id=repo.id,
            title="Retry budget stays capped",
            content="Enrollment retry_logic must stay capped at three attempts to avoid duplicate writes.",
            summary="Keep retry budget bounded for enrollment sync.",
            memory_type="decision",
        )
    )
    services["memory"].link_memory(
        MemoryLinkCreate(
            from_memory_id=memory.id,
            to_node_kind="symbol",
            to_node_id=symbol.id,
            edge_type="APPLIES_TO",
        )
    )

    payload = services["retrieval"].retrieve(
        query="refactor retry logic and surface prior decisions",
        mode="refactor",
        repo=repo,
    )

    assert payload["context"]["symbols"]
    assert any(item["title"] == "Retry budget stays capped" for item in payload["context"]["memories"])
    assert any(snippet["symbol"] == "retry_logic" for snippet in payload["context"]["snippets"])


def test_indexing_creates_test_coverage_edges(db_session, sample_repo) -> None:
    services = build_services(db_session)
    repo = services["repos"].add_repo(RepoCreate(name="sample", local_path=str(sample_repo)))
    services["indexing"].index_repo(repo)

    edges = db_session.query(Edge).filter(Edge.repo_id == repo.id, Edge.edge_type == EdgeType.test_covers_symbol).all()
    assert edges
    assert any(edge.from_node_kind == "file" and edge.to_node_kind == "symbol" for edge in edges)


def test_indexing_creates_doc_description_edges(db_session, sample_repo) -> None:
    services = build_services(db_session)
    repo = services["repos"].add_repo(RepoCreate(name="sample", local_path=str(sample_repo)))
    services["indexing"].index_repo(repo)

    symbol_edges = db_session.query(Edge).filter(
        Edge.repo_id == repo.id, Edge.edge_type == EdgeType.doc_describes_symbol
    ).all()
    file_edges = db_session.query(Edge).filter(
        Edge.repo_id == repo.id, Edge.edge_type == EdgeType.doc_describes_file
    ).all()
    assert symbol_edges
    assert file_edges
    assert any(edge.from_node_kind == "file" and edge.to_node_kind == "symbol" for edge in symbol_edges)
    assert any(edge.from_node_kind == "file" and edge.to_node_kind == "file" for edge in file_edges)


def test_indexing_creates_config_affects_file_edges(db_session, sample_repo) -> None:
    services = build_services(db_session)
    repo = services["repos"].add_repo(RepoCreate(name="sample", local_path=str(sample_repo)))
    services["indexing"].index_repo(repo)

    edges = db_session.query(Edge).filter(Edge.repo_id == repo.id, Edge.edge_type == EdgeType.config_affects_file).all()
    assert edges
    assert any(edge.from_node_kind == "file" and edge.to_node_kind == "file" for edge in edges)


def test_retrieve_persists_diagnostics_in_retrieval_log(db_session, sample_repo) -> None:
    services = build_services(db_session)
    repo = services["repos"].add_repo(RepoCreate(name="sample", local_path=str(sample_repo)))
    services["indexing"].index_repo(repo)

    payload = services["retrieval"].retrieve(
        query="Where is retry logic configured and tested?",
        mode="bugfix",
        repo=repo,
        include_code=False,
    )

    assert "stage_counts" in payload["diagnostics"]
    log = db_session.query(RetrievalLog).order_by(RetrievalLog.id.desc()).first()
    assert log is not None
    assert log.diagnostics_json["stage_counts"]["lexical"]["files"] >= 0
    assert log.diagnostics_json["ranked_candidates"]
