"""Async SQLAlchemy database setup."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


def _make_async_url(url: str) -> str:
    if "postgresql+psycopg://" in url and "psycopg_asyncio" not in url:
        return url.replace("postgresql+psycopg://", "postgresql+psycopg_asyncio://")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg_asyncio://")
    return url


_engine = None
_session_maker = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(_make_async_url(settings.DATABASE_URL), echo=False)
    return _engine


def _get_session_maker():
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(_get_engine(), expire_on_commit=False)
    return _session_maker


async def get_db() -> AsyncIterator[AsyncSession]:
    async with _get_session_maker()() as session:
        yield session
