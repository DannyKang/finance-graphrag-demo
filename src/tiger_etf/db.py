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

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_schema() -> None:
    """Create the tiger_etf schema and all tables."""
    from tiger_etf.models import Base

    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS tiger_etf"))
        conn.commit()
    Base.metadata.create_all(engine)
