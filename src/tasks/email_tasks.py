import uuid
from celery import Task
from celery.utils.log import get_task_logger

from src.workers.celery_app import celery_app
from src.core.config import settings
from src.core.exceptions import ValidationError

logger = get_task_logger(__name__)

class BaseTask(Task):
    """
    Clase base para todas las tareas Celery del sistema.
    Centraliza el manejo de reintentos y actualización de estado en DB.
    """

    abstract = True
    max_retries = settings.celery_task_max_retries

    def on_failure(self, exc: Exception, task_id: str, args, kwargs, einfo) -> None:
        """
        Hook ejecutado cuando la tarea falla de forma definitiva.

        **Args:**
            exc: Excepción que causó el fallo.
            task_id: ID de la tarea fallida.
            args: Argumentos posicionales de la tarea.
            kwargs: Argumentos keyword de la tarea.
            einfo: Información del traceback.
        """
        logger.error("task_permanent_failure", task_id=task_id, error=str(exc))

    def on_retry(self, exc: Exception, task_id: str, args, kwargs, einfo) -> None:
        """
        Hook ejecutado cada vez que una tarea se reintenta.

        **Args:**
            exc: Excepción que disparó el reintento.
            task_id: ID de la tarea.
            args: Argumentos posicionales de la tarea.
            kwargs: Argumentos keyword de la tarea.
            einfo: Información del traceback.
        """
        logger.warning("task_retrying", task_id=task_id, error=str(exc))

    def on_success(self, retval, task_id: str, args, kwargs) -> None:
        """
        Hook ejecutado cuando la tarea finaliza con éxito.

        **Args:**
            retval: Valor de retorno de la tarea.
            task_id: ID de la tarea exitosa.
            args: Argumentos posicionales de la tarea.
            kwargs: Argumentos keyword de la tarea.
        """
        logger.info("task_success", task_id=task_id)

@celery_app.task(
    bind=True,
    base=BaseTask,
    queue="emails",
    name="src.tasks.email_tasks.send_email",
)
def send_email(self, job_id: str, payload: dict) -> dict:
    """
    Procesa el envío de un email de forma asíncrona.
    Reintenta automáticamente ante fallos transitorios con backoff exponencial.

    **Args:**
        job_id: UUID del job asociado a esta tarea.
        payload: Diccionario con recipient, subject y body validados.

    **Returns:**
        Diccionario con el resultado del envío y el job_id.

    **Raises:**
        ValidationError: Si el payload no contiene los campos requeridos.
        self.retry: Si ocurre un error transitorio durante el envío.
    """
    required_fields = {"recipient", "subject", "body"}
    if missing := required_fields - payload.keys():
        raise ValidationError(f"Campos faltantes en payload: {missing}")

    try:
        logger.info(
            "sending_email",
            job_id=job_id,
            recipient=payload["recipient"],
        )

        # Aquí se integraría el cliente SMTP real (smtplib, SendGrid, etc.)
        # Por ahora simula el envío para mantener el foco en la arquitectura
        result = {
            "job_id": job_id,
            "recipient": payload["recipient"],
            "status": "sent",
        }

        logger.info("email_sent", job_id=job_id, recipient=payload["recipient"])
        return result

    except Exception as exc:
        logger.warning("email_send_failed", job_id=job_id, error=str(exc))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)