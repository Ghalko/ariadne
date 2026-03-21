from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import create_engine
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
