from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.core.config import settings
from src.core.cors import CORS_CONFIG
from src.core.logging import setup_logging, get_logger
from src.core.rate_limiter import limiter
from src.core.security_middleware import WAFMiddleware, SecurityHeadersMiddleware
from src.utils.file_utils import ensure_tmp_dirs
from src.workers.beat_schedule import register_beat_schedule
from src.api.routes import router
from src.api.auth_routes import router as auth_router

from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from src.core.metrics import REGISTRY
from src.core.metrics_middleware import MetricsMiddleware

setup_logging()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Maneja el ciclo de vida de la aplicación.
    Se ejecuta al arrancar y al apagar el servidor.
    """
    ensure_tmp_dirs()
    logger.info("app_started", environment=settings.environment)
    yield
    logger.info("app_shutdown")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Middlewares
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(WAFMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(CORSMiddleware, **CORS_CONFIG)
app.add_middleware(MetricsMiddleware)

app.include_router(router)
app.include_router(auth_router)

@app.get("/health", tags=["monitoring"])
def health_check():
    """
    Endpoint de health check básico para load balancers y monitoreo externo.

    **Returns:**
        Diccionario con el estado de la aplicación.
    """
    return {"status": "ok", "app": settings.app_name}

@app.get("/metrics", include_in_schema=False)
def metrics():
    """
    Endpoint que expone las métricas en formato Prometheus.
    Consulta la DB para actualizar los gauges antes de responder.

    **Returns:**
        Métricas en formato texto plano compatible con Prometheus.
    """
    from src.core.database import SessionLocal
    from src.services.metrics_service import refresh_job_status_metrics

    db = SessionLocal()
    try:
        refresh_job_status_metrics(db)
    finally:
        db.close()

    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )