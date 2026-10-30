from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from src.core.config import settings

# Convert postgresql:// to postgresql+asyncpg:// for async driver
database_url = str(settings.database_url).replace(
    "postgresql://", "postgresql+asyncpg://", 1
)

engine = create_async_engine(
    database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,  # Verifica la conexión antes de usarla
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async generator que provee una sesión de DB por request y garantiza su cierre.
    Usado como dependencia de FastAPI con Depends().

    **Yields:**
        Sesión activa de SQLAlchemy AsyncSession.
    """
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_worker_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager que provee una sesión de DB para uso en workers de Celery.
    A diferencia de get_db(), no depende del ciclo de vida de FastAPI.

    **Yields:**
        Sesión activa de SQLAlchemy AsyncSession.

    **Raises:**
        Exception: Cualquier error durante la sesión hace rollback automático.
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
