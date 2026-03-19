from sqlalchemy.orm import Session
from src.core.logging import get_logger
from src.models.audit_log import AuditLog

logger = get_logger(__name__)

def log_action(
    db: Session,
    action: str,
    resource: str,
    resource_id: str | None = None,
    user_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    extra: dict | None = None,
) -> None:
    """
    Registra una acción en el log de auditoría de forma no bloqueante.
    Si el registro falla no lanza excepción — la auditoría nunca debe
    interrumpir el flujo principal de la aplicación.

    **Args:**
        db: Sesión activa de SQLAlchemy.
        action: Acción realizada (ej: "enqueue_job", "login", "logout").
        resource: Recurso afectado (ej: "job", "user").
        resource_id: ID del recurso afectado si aplica.
        user_id: UUID del usuario que realizó la acción.
        ip_address: IP del cliente que realizó la acción.
        user_agent: User-Agent del cliente.
        extra: Datos adicionales relevantes para el contexto.
    """
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent[:255] if user_agent else None,
            extra=extra,
        )
        db.add(entry)
        db.commit()
        logger.debug("audit_logged", action=action, resource=resource, user_id=user_id)

    except Exception as exc:
        db.rollback()
        logger.warning("audit_log_failed", action=action, error=str(exc))