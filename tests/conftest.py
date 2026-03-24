from __future__ import annotations

from pathlib import Path

import pytest

from ariadne_index.config import get_settings
from ariadne_index.db import init_database, session_scope


@pytest.fixture(autouse=True)
def deterministic_embeddings(monkeypatch):
    monkeypatch.setenv("ARIADNE_EMBEDDING_PROVIDER", "deterministic")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def database_url(tmp_path: Path) -> str:
    return f"sqlite+pysqlite:///{tmp_path / 'ariadne.db'}"


@pytest.fixture()
def sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "sample_repo"
    repo.mkdir()
    (repo / "app").mkdir()
    (repo / "config").mkdir()
    (repo / "tests").mkdir()
    (repo / "docs").mkdir()
    (repo / "app" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "app" / "worker.py").write_text(
        "from app.service import retry_logic\n\n"
        "def run_worker(payload):\n"
        "    return retry_logic(payload)\n",
        encoding="utf-8",
    )
    (repo / "app" / "service.py").write_text(
        '"""Enrollment retry helpers."""\n\n'
        "def retry_logic(payload, attempts=3):\n"
        '    """Retry enrollment sync with a bounded budget."""\n'
        "    for _ in range(attempts):\n"
        "        if payload:\n"
        "            return True\n"
        "    return False\n",
        encoding="utf-8",
    )
    (repo / "tests" / "test_service.py").write_text(
        "from app.service import retry_logic\n\n"
        "def test_retry_logic():\n"
        "    assert retry_logic({'id': '123'}) is True\n",
        encoding="utf-8",
    )
    (repo / "docs" / "adr-retry.md").write_text(
        "# Retry Decision\n\nBound enrollment sync retries to avoid duplicate writes.\n",
        encoding="utf-8",
    )
    (repo / "config" / "retry.toml").write_text(
        '[retry_logic]\nmodule = "app.service"\nattempts = 3\nstrategy = "bounded"\n',
        encoding="utf-8",
    )
    return repo


@pytest.fixture()
def initialized_db(database_url: str):
    init_database(database_url)
    return database_url


@pytest.fixture()
def db_session(initialized_db: str):
    with session_scope(initialized_db) as session:
        yield session
