from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from ariadne_index.config import get_settings
from ariadne_index.models.base import Base


def build_engine(database_url: str | None = None):
    settings = get_settings()
    url = database_url or settings.database_url
    return create_engine(url, future=True)


def build_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    engine = build_engine(database_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_database(database_url: str | None = None) -> None:
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)


def database_diagnostics(database_url: str | None = None) -> dict:
    engine = build_engine(database_url)
    return database_diagnostics_for_engine(engine)


def database_diagnostics_for_engine(engine: Engine) -> dict:
    inspector = inspect(engine)
    settings = get_settings()
    diagnostics = {
        "database_url": str(engine.url),
        "dialect": engine.dialect.name,
        "tables": sorted(inspector.get_table_names()),
        "embedding_dimensions_configured": settings.embedding_dimensions,
        "embedding_provider": settings.embedding_provider,
        "issues": [],
    }

    embeddings_exists = "embeddings" in diagnostics["tables"]
    retrieval_logs_exists = "retrieval_logs" in diagnostics["tables"]
    diagnostics["embeddings_table_present"] = embeddings_exists
    diagnostics["retrieval_logs_table_present"] = retrieval_logs_exists

    if retrieval_logs_exists:
        retrieval_log_columns = {column["name"] for column in inspector.get_columns("retrieval_logs")}
        diagnostics["retrieval_logs_columns"] = sorted(retrieval_log_columns)
        if "diagnostics_json" not in retrieval_log_columns:
            diagnostics["issues"].append(
                "retrieval_logs.diagnostics_json is missing; run alembic upgrade head"
            )

    if not embeddings_exists:
        return diagnostics

    embedding_columns = {column["name"] for column in inspector.get_columns("embeddings")}
    diagnostics["embedding_columns"] = sorted(embedding_columns)

    with engine.connect() as connection:
        if engine.dialect.name == "postgresql":
            extension_present = bool(
                connection.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar()
            )
            diagnostics["vector_extension_present"] = extension_present
            if not extension_present:
                diagnostics["issues"].append("pgvector extension is not installed")

            vector_type = connection.execute(
                text(
                    """
                    SELECT format_type(a.atttypid, a.atttypmod)
                    FROM pg_attribute a
                    JOIN pg_class c ON c.oid = a.attrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.relname = 'embeddings'
                      AND a.attname = 'vector'
                      AND a.attnum > 0
                      AND NOT a.attisdropped
                    """
                )
            ).scalar()
            diagnostics["embedding_vector_type"] = vector_type
            vector_dimensions = _parse_vector_dimensions(vector_type)
            diagnostics["embedding_vector_dimensions"] = vector_dimensions
            if vector_dimensions is not None and vector_dimensions != settings.embedding_dimensions:
                diagnostics["issues"].append(
                    f"configured embedding dimensions ({settings.embedding_dimensions}) "
                    f"do not match DB vector type ({vector_dimensions})"
                )

        stored_dimensions = {
            row[0]
            for row in connection.execute(text("SELECT DISTINCT dimensions FROM embeddings"))
            if row[0] is not None
        }
        diagnostics["stored_embedding_dimensions"] = sorted(stored_dimensions)
        if stored_dimensions and settings.embedding_dimensions not in stored_dimensions:
            diagnostics["issues"].append(
                f"configured embedding dimensions ({settings.embedding_dimensions}) "
                f"do not match stored embeddings ({sorted(stored_dimensions)})"
            )

    return diagnostics


def compatibility_issues_for_engine(engine: Engine) -> list[str]:
    diagnostics = database_diagnostics_for_engine(engine)
    return list(diagnostics["issues"])


def _parse_vector_dimensions(vector_type: str | None) -> int | None:
    if not vector_type or "(" not in vector_type or ")" not in vector_type:
        return None
    suffix = vector_type.rsplit("(", 1)[-1].rstrip(")")
    try:
        return int(suffix)
    except ValueError:
        return None


@contextmanager
def session_scope(database_url: str | None = None) -> Iterator[Session]:
    factory = build_session_factory(database_url)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
