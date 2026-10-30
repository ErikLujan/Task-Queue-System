import redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


def check_redis() -> dict:
    """
    Verifica la conectividad con Redis haciendo un ping.

    **Returns:**
        Diccionario con el estado y latencia de Redis.
    """
    try:
        client = redis.from_url(str(settings.redis_url), socket_connect_timeout=2)
        client.ping()
        return {"status": "ok"}
    except Exception as exc:
        logger.warning("redis_health_failed", error=str(exc))
        return {"status": "error", "detail": str(exc)}


async def check_database(db: AsyncSession) -> dict:
    """
    Verifica la conectividad con la base de datos ejecutando una query mínima.

    **Args:**
        db: Sesión activa de SQLAlchemy AsyncSession.

    **Returns:**
        Diccionario con el estado de la base de datos.
    """
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        logger.warning("db_health_failed", error=str(exc))
        return {"status": "error", "detail": str(exc)}


async def full_health_report(db: AsyncSession) -> dict:
    """
    Genera un reporte completo del estado de todos los servicios.

    **Args:**
        db: Sesión activa de SQLAlchemy AsyncSession.

    **Returns:**
        Diccionario con el estado consolidado de Redis y la base de datos.
    """
    report = {
        "redis": check_redis(),
        "database": await check_database(db),
    }
    overall = "ok" if all(v["status"] == "ok" for v in report.values()) else "degraded"
    return {"status": overall, "services": report}
