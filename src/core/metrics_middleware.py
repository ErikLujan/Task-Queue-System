import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from src.core.metrics import HTTP_REQUESTS_TOTAL, HTTP_REQUEST_DURATION_SECONDS

_EXCLUDED_PATHS = {"/metrics", "/health", "/docs", "/redoc", "/openapi.json"}

class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware que registra métricas HTTP de cada request.
    Excluye endpoints de infraestructura para no contaminar los datos.
    """

    async def dispatch(self, request: Request, call_next):
        """
        Intercepta cada request, mide su duración y registra las métricas.

        **Args:**
            request: Request HTTP entrante.
            call_next: Función que pasa el request al siguiente middleware.

        **Returns:**
            Response original con métricas registradas.
        """
        path = request.url.path

        if path in _EXCLUDED_PATHS:
            return await call_next(request)

        normalized_path = _normalize_path(path) # --> Normaliza paths con IDs para no generar una métrica por cada UUID

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            endpoint=normalized_path,
            status_code=response.status_code,
        ).inc()

        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=request.method,
            endpoint=normalized_path,
        ).observe(duration)

        return response

def _normalize_path(path: str) -> str:
    """
    Reemplaza segmentos que parecen UUIDs por un placeholder genérico.
    Evita alta cardinalidad en las métricas por paths dinámicos.

    **Args:**
        path: Path del request a normalizar.

    **Returns:**
        Path con UUIDs reemplazados por {id}.
    """
    import re
    uuid_pattern = re.compile(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        re.IGNORECASE,
    )
    return uuid_pattern.sub("{id}", path)