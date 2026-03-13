from src.core.config import settings

# En producción los allowed_origins deben ser dominios reales explícitos
# En desarrollo permitimos localhost en puertos comunes
_DEV_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
]

CORS_CONFIG = {
    "allow_origins": _DEV_ORIGINS if settings.environment == "development" else [],
    "allow_credentials": False,       # Sin cookies ni auth headers cross-origin
    "allow_methods": ["GET", "POST"], # Solo los métodos que usa la API
    "allow_headers": ["Content-Type", "Accept"],
    "max_age": 600,                   # Cache del preflight por 10 minutos
}