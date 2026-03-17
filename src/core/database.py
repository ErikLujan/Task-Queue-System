from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.core.config import settings

engine = create_engine(
    str(settings.database_url),
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,  # --> Verifica la conexión antes de usarla
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def get_db() -> Generator[Session, None, None]:
    """
    Generador que provee una sesión de DB por request y garantiza su cierre.
    Usado como dependencia de FastAPI con Depends().

    **Yields:**
        Sesión activa de SQLAlchemy.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_worker_db() -> Generator[Session, None, None]:
    """
    Context manager que provee una sesión de DB para uso en workers de Celery.
    A diferencia de get_db(), no depende del ciclo de vida de FastAPI.

    **Yields:**
        Sesión activa de SQLAlchemy.

    **Raises:**
        Exception: Cualquier error durante la sesión hace rollback automático.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()