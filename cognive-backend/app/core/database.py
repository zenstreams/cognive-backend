"""Database setup for Cognive Control Plane (PostgreSQL 15+ / TimescaleDB).

This module provides:
- SQLAlchemy engine + session factory (sync and async)
- FastAPI dependencies to get DB sessions
- Lightweight connectivity checks for readiness probes
"""

from __future__ import annotations

from contextlib import contextmanager
from itertools import cycle
from threading import Lock
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def parse_csv_urls(value: str | None) -> list[str]:
    if not value:
        return []
    # allow commas + newlines; trim whitespace; drop empties
    return [part.strip() for part in value.replace("\n", ",").split(",") if part.strip()]


def create_db_engine(database_url: str | None = None) -> Engine:
    """Create a production-leaning SQLAlchemy engine with connection pooling."""
    url = database_url or settings.database_url
    # Pool sizing per SCRUM-52 notes: 20 pool + 10 overflow.
    return create_engine(
        url,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=1800,
        future=True,
    )


write_engine: Engine = create_db_engine()
engine: Engine = write_engine  # backwards compat alias

WriteSessionLocal = sessionmaker(bind=write_engine, autocommit=False, autoflush=False, future=True)

_read_urls = parse_csv_urls(settings.database_read_urls)
_read_engines: list[Engine] = [create_db_engine(u) for u in _read_urls] if _read_urls else []
_read_engine_cycle = cycle(_read_engines) if _read_engines else None
_read_engine_lock = Lock()


def get_read_engine() -> Engine:
    """Return a read engine if configured; otherwise fall back to the primary."""
    if not _read_engine_cycle:
        return write_engine
    with _read_engine_lock:
        return next(_read_engine_cycle)


def get_read_engine_entries() -> list[tuple[str, Engine]]:
    """Return (url, engine) pairs for all configured read engines."""
    return list(zip(_read_urls, _read_engines, strict=False))


def create_read_sessionmaker() -> sessionmaker[Session]:
    """Create a sessionmaker bound to the next read engine (round-robin)."""
    return sessionmaker(bind=get_read_engine(), autocommit=False, autoflush=False, future=True)


SessionLocal = WriteSessionLocal  # backwards compat alias


def create_async_db_engine(database_url: str | None = None) -> AsyncEngine:
    """Create an async SQLAlchemy engine (asyncpg) with connection pooling."""
    url = database_url or settings.database_url_async
    if not url:
        raise ValueError("Async database URL not configured. Set DATABASE_URL_ASYNC.")
    if not url.lower().startswith("postgresql+asyncpg://"):
        raise ValueError("DATABASE_URL_ASYNC must start with 'postgresql+asyncpg://'.")
    return create_async_engine(
        url,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=1800,
        future=True,
    )


async_write_engine: AsyncEngine = create_async_db_engine()
async_engine: AsyncEngine = async_write_engine  # backwards compat alias
AsyncWriteSessionLocal = async_sessionmaker(
    bind=async_write_engine, autoflush=False, autocommit=False, expire_on_commit=False
)

_read_urls_async = parse_csv_urls(settings.database_read_urls_async)
_async_read_engines: list[AsyncEngine] = (
    [create_async_db_engine(u) for u in _read_urls_async] if _read_urls_async else []
)
_async_read_engine_cycle = cycle(_async_read_engines) if _async_read_engines else None
_async_read_engine_lock = Lock()


def get_async_read_engine() -> AsyncEngine:
    """Return an async read engine if configured; otherwise fall back to the primary."""
    if not _async_read_engine_cycle:
        return async_write_engine
    with _async_read_engine_lock:
        return next(_async_read_engine_cycle)


def get_async_read_engine_entries() -> list[tuple[str, AsyncEngine]]:
    """Return (url, engine) pairs for all configured async read engines."""
    return list(zip(_read_urls_async, _async_read_engines, strict=False))


AsyncSessionLocal = AsyncWriteSessionLocal  # backwards compat alias


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context-managed DB session (useful for scripts/tasks)."""
    session: Session = WriteSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session."""
    session: Session = WriteSessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_db_read() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a *read-preferred* DB session."""
    ReadSessionLocal = create_read_sessionmaker()
    session: Session = ReadSessionLocal()
    try:
        yield session
    finally:
        session.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    async with AsyncWriteSessionLocal() as session:
        yield session


async def get_async_db_read() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async *read-preferred* DB session."""
    async_session_factory = async_sessionmaker(
        bind=get_async_read_engine(), autoflush=False, autocommit=False, expire_on_commit=False
    )
    async with async_session_factory() as session:
        yield session


def check_database_connectivity() -> None:
    """Raises on DB connectivity failure; used by readiness checks."""
    with write_engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def check_read_database_connectivity() -> None:
    """Raises on replica connectivity failure; falls back to primary if not configured."""
    with get_read_engine().connect() as conn:
        conn.execute(text("SELECT 1"))


async def check_database_connectivity_async() -> None:
    """Async connectivity check; preferred for async endpoints."""
    async with async_write_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def check_read_database_connectivity_async() -> None:
    """Async connectivity check for replicas; falls back to primary if not configured."""
    async with get_async_read_engine().connect() as conn:
        await conn.execute(text("SELECT 1"))


