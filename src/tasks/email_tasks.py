import time
import uuid
from celery import Task

from src.workers.celery_app import celery_app
from src.core.config import settings
from src.core.database import get_worker_db
from src.core.logging import get_logger
from src.core.exceptions import ValidationError
from src.core.metrics import (
    JOBS_TOTAL,
    JOB_PROCESSING_SECONDS,
    JOB_ERRORS_TOTAL,
    JOB_RETRIES_TOTAL,
)
from src.models.job import JobStatus

logger = get_logger(__name__)

_job_start_times: dict[str, float] = {}

def update_job_state(job_id: str, status: JobStatus, result: dict | None = None, error: str | None = None, webhook_url: str | None = None, job_type: str | None = None) -> None:
    """
    Actualiza el estado de un job en la DB desde el contexto de un worker.
    Función auxiliar compartida por todas las tasks.

    **Args:**
        job_id: UUID del job a actualizar como string.
        status: Nuevo estado a asignar al job.
        result: Resultado de la tarea si fue exitosa.
        error: Mensaje de error si la tarea falló.
        webhook_url: URL opcional para notificar el resultado.
        job_type: Tipo de job para métricas (email, image, report).
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

    if status == JobStatus.RUNNING:
        _job_start_times[job_id] = time.perf_counter()

    # Registrar métricas en estados finales
    if job_type and status in (JobStatus.SUCCESS, JobStatus.FAILURE):
        duration = time.perf_counter() - _job_start_times.pop(job_id, time.perf_counter())
        JOB_PROCESSING_SECONDS.labels(job_type=job_type, status=status.value).observe(duration)

        if status == JobStatus.FAILURE:
            JOB_ERRORS_TOTAL.labels(job_type=job_type).inc()

    if job_type and status == JobStatus.RETRYING:
        JOB_RETRIES_TOTAL.labels(job_type=job_type).inc()

    if webhook_url and status in (JobStatus.SUCCESS, JobStatus.FAILURE):
        from src.services.webhook_service import dispatch_webhook
        dispatch_webhook(
            webhook_url=str(webhook_url),
            payload={
                "job_id": job_id,
                "status": status.value,
                "result": result,
                "error": error,
            },
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
        payload = kwargs.get("payload", {})
        webhook_url = payload.get("webhook_url")
        job_type = payload.get("job_type")
        if job_id:
            update_job_state(job_id, JobStatus.FAILURE, error=str(exc), webhook_url=webhook_url, job_type=job_type)
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
        job_type = kwargs.get("payload", {}).get("job_type")
        if job_id:
            update_job_state(job_id, JobStatus.RETRYING, job_type=job_type)
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

    webhook_url = payload.get("webhook_url")
    JOBS_TOTAL.labels(job_type="email").inc()
    update_job_state(job_id, JobStatus.RUNNING, job_type="email")

    try:
        logger.info("sending_email", job_id=job_id, recipient=payload["recipient"])

        result = {
            "job_id": job_id,
            "recipient": payload["recipient"],
            "status": "sent",
        }

        update_job_state(job_id, JobStatus.SUCCESS, result=result, webhook_url=webhook_url, job_type="email")
        logger.info("email_sent", job_id=job_id, recipient=payload["recipient"])
        return result

    except Exception as exc:
        logger.warning("email_send_failed", job_id=job_id, error=str(exc))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)