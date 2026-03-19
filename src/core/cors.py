import os
from src.core.config import settings

_DEV_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
]

def _get_origins() -> list[str]:
    """
    Retorna los orígenes permitidos según el entorno.
    En producción lee desde la variable ALLOWED_ORIGINS.

    **Returns:**
        Lista de orígenes permitidos para CORS.
    """
    if settings.environment == "production":
        origins = os.getenv("ALLOWED_ORIGINS", "")
        return [o.strip() for o in origins.split(",") if o.strip()]
    return _DEV_ORIGINS

CORS_CONFIG = {
    "allow_origins": _get_origins(),
    "allow_credentials": False,
    "allow_methods": ["GET", "POST"],
    "allow_headers": ["Content-Type", "Accept"],
    "max_age": 600,     
}