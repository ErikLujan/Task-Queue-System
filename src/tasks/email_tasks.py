import uuid
from celery import Task

from src.workers.celery_app import celery_app
from src.core.config import settings
from src.core.database import get_worker_db
from src.core.logging import get_logger
from src.core.exceptions import ValidationError
from src.models.job import JobStatus

logger = get_logger(__name__)

def update_job_state(job_id: str, status: JobStatus, result: dict | None = None, error: str | None = None) -> None:
    """
    Actualiza el estado de un job en la DB desde el contexto de un worker.
    Función auxiliar compartida por todas las tasks.

    **Args:**
        job_id: UUID del job a actualizar como string.
        status: Nuevo estado a asignar al job.
        result: Resultado de la tarea si fue exitosa.
        error: Mensaje de error si la tarea falló.
    """
    from src.services.queue_service import update_job_status
    with get_worker_db() as db:
        update_job_status(
            db=db,
            job_id=uuid.UUID(job_id),
            status=status,
            result=result,
            error_message=error,
        )

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
        job_id = kwargs.get("job_id")
        if job_id:
            update_job_state(job_id, JobStatus.FAILURE, error=str(exc))
        logger.error("task_permanent_failure", tid=task_id, error=str(exc))

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
        job_id = kwargs.get("job_id")
        if job_id:
            update_job_state(job_id, JobStatus.RETRYING)
        logger.warning("task_retrying", tid=task_id, error=str(exc))

    def on_success(self, retval, task_id: str, args, kwargs) -> None:
        """
        Hook ejecutado cuando la tarea finaliza con éxito.

        **Args:**
            retval: Valor de retorno de la tarea.
            task_id: ID de la tarea exitosa.
            args: Argumentos posicionales de la tarea.
            kwargs: Argumentos keyword de la tarea.
        """
        logger.info("task_success", tid=task_id)

@celery_app.task(
    bind=True,
    base=BaseTask,
    queue="emails",
    name="src.tasks.email_tasks.send_email",
)
def send_email(self, job_id: str, payload: dict) -> dict:
    """
    Procesa el envío de un email de forma asíncrona.
    Actualiza el estado del job en DB en cada etapa del procesamiento.

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

    update_job_state(job_id, JobStatus.RUNNING)

    try:
        logger.info("sending_email", job_id=job_id, recipient=payload["recipient"])

        result = {
            "job_id": job_id,
            "recipient": payload["recipient"],
            "status": "sent",
        }

        update_job_state(job_id, JobStatus.SUCCESS, result=result)
        logger.info("email_sent", job_id=job_id, recipient=payload["recipient"])
        return result

    except Exception as exc:
        logger.warning("email_send_failed", job_id=job_id, error=str(exc))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)