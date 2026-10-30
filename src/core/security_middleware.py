from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from typing import Callable, Awaitable
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware que limita el tamaño máximo del body de las requests.
    Previene ataques de denegación de servicio por payloads excesivamente grandes.
    """

    def __init__(self, app, max_size_bytes: int | None = None):
        super().__init__(app)
        self.max_size_bytes = max_size_bytes or settings.max_file_size_bytes

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable]
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size_bytes:
            logger.warning(
                "request_body_too_large",
                path=request.url.path,
                size=content_length,
                max_size=self.max_size_bytes,
            )
            return JSONResponse(
                status_code=413,
                content={"detail": "Payload demasiado grande."},
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Agrega headers de seguridad HTTP a todas las respuestas.
    Protege contra clickjacking, XSS, sniffing de contenido y más.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Inyecta security headers en cada response saliente.

        **Args:**
            request: Request HTTP entrante.
            call_next: Función que pasa el request al siguiente middleware o handler.

        **Returns:**
            Response con headers de seguridad agregados.
        """
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
            "img-src 'self' data: fastapi.tiangolo.com; "
            "font-src 'self' data: cdn.jsdelivr.net;"
        )
        response.headers["Cache-Control"] = "no-store"
        return response
