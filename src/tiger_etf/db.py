from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from tiger_etf.config import settings

engine = create_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

# Reader engine: falls back to writer if not configured
_reader_url = settings.database_url_reader or settings.database_url
engine_reader = create_engine(
    _reader_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
SessionLocalReader = sessionmaker(bind=engine_reader, expire_on_commit=False)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Get a read-write session (writer endpoint)."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_reader_session() -> Generator[Session, None, None]:
    """Get a read-only session (reader endpoint)."""
    session = SessionLocalReader()
    try:
        yield session
    finally:
        session.close()


def init_schema() -> None:
    """Create the tiger_etf schema and all tables."""
    from tiger_etf.models import Base

    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS tiger_etf"))
        conn.commit()
    Base.metadata.create_all(engine)
