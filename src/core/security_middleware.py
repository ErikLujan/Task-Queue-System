import re
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from src.core.logging import get_logger

logger = get_logger(__name__)

# Patrones WAF — detectan intentos de ataque en URLs, headers y query params
_WAF_PATTERNS = [
    re.compile(r"(union\s+select|insert\s+into|drop\s+table|delete\s+from)", re.IGNORECASE),
    re.compile(r"(<script|javascript:|onerror=|onload=|eval\()", re.IGNORECASE),
    re.compile(r"(\.\./|\.\.\\|%2e%2e%2f|%2e%2e/)", re.IGNORECASE),
    re.compile(r"(etc/passwd|etc/shadow|proc/self)", re.IGNORECASE),
    re.compile(r"(\x00|%00)", re.IGNORECASE),
]

# Tamaño máximo del body permitido — 1MB
_MAX_BODY_SIZE = 1 * 1024 * 1024

class WAFMiddleware(BaseHTTPMiddleware):
    """
    Middleware que actúa como Web Application Firewall básico.
    Inspecciona URL, query string y headers en busca de patrones maliciosos.
    """

    async def dispatch(self, request: Request, call_next):
        """
        Intercepta cada request y lo analiza antes de pasarlo al handler.

        **Args:**
            request: Request HTTP entrante.
            call_next: Función que pasa el request al siguiente middleware o handler.

        **Returns:**
            Response original si el request es seguro.

        **Raises:**
            JSONResponse 400: Si se detecta un patrón malicioso.
            JSONResponse 413: Si el body supera el tamaño máximo permitido.
        """
        # Validar tamaño del body
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > _MAX_BODY_SIZE:
            logger.warning("waf_body_too_large", path=request.url.path, size=content_length)
            return JSONResponse(
                status_code=413,
                content={"detail": "Payload demasiado grande."},
            )

        # Inspeccionar URL completa y query string
        full_url = str(request.url)
        for pattern in _WAF_PATTERNS:
            if pattern.search(full_url):
                logger.warning("waf_blocked_url", path=request.url.path, pattern=pattern.pattern)
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Request bloqueado."},
                )

        # Inspeccionar headers sospechosos
        for header_value in request.headers.values():
            for pattern in _WAF_PATTERNS:
                if pattern.search(header_value):
                    logger.warning("waf_blocked_header", pattern=pattern.pattern)
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Request bloqueado."},
                    )

        return await call_next(request)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Agrega headers de seguridad HTTP a todas las respuestas.
    Protege contra clickjacking, XSS, sniffing de contenido y más.
    """

    async def dispatch(self, request: Request, call_next):
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
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
            "img-src 'self' data: fastapi.tiangolo.com; "
            "font-src 'self' data: cdn.jsdelivr.net;"
        )
        response.headers["Cache-Control"] = "no-store"
        return response