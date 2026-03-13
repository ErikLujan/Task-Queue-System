import logging
import structlog
from src.core.config import settings

def setup_logging() -> None:
    """
    Configura structlog con procesadores adecuados según el entorno.
    En desarrollo usa salida legible; en producción usa JSON estructurado.
    """
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.environment == "development":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Retorna un logger con nombre de módulo para trazabilidad.

    **Args**:
        name: Nombre del módulo, usualmente __name__.

    **Returns**:
        Logger configurado listo para usar.
    """
    return structlog.get_logger(name)