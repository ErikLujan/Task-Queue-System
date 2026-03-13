import uuid
from sqlalchemy.orm import Session

from src.core.exceptions import TaskEnqueueError, TaskNotFoundError
from src.core.logging import get_logger
from src.models.job import Job, JobStatus, JobType
from src.schemas.task_payload import EmailTaskPayload, ImageTaskPayload, ReportTaskPayload
from src.workers.celery_app import celery_app

logger = get_logger(__name__)

# Mapeo de JobType a nombre de tarea Celery — evita que haya strings sueltos
_TASK_NAME_MAP: dict[JobType, str] = {
    JobType.EMAIL:  "src.tasks.email_tasks.send_email",
    JobType.IMAGE:  "src.tasks.image_tasks.process_image",
    JobType.REPORT: "src.tasks.report_tasks.generate_report",
}

PayloadType = EmailTaskPayload | ImageTaskPayload | ReportTaskPayload

def enqueue_job(db: Session, job_type: JobType, payload: PayloadType) -> Job:
    """
    Persiste un job en la base de datos y lo encola en Celery de forma atómica.
    Si el encolado falla, el job queda en estado PENDING para reintento manual.

    **Args:**
        db: Sesión activa de SQLAlchemy.
        job_type: Tipo de tarea a ejecutar.
        payload: Schema validado con los datos de la tarea.

    **Returns:**
        Instancia del Job persistido con su ID asignado.

    **Raises:**
        TaskEnqueueError: Si Celery no puede recibir la tarea.
    """
    # Normalizamos a instancia de JobType por si llega como string
    if isinstance(job_type, str):
        job_type = JobType(job_type)

    job = Job(
        job_type=job_type.value,
        status=JobStatus.PENDING.value,
        payload=payload.model_dump(),
    )
    db.add(job)
    db.flush()

    try:
        task_name = _TASK_NAME_MAP[job_type]
        celery_task = celery_app.send_task(
            task_name,
            kwargs={"job_id": str(job.id), "payload": payload.model_dump()},
            queue=job_type.value + "s",
        )
        job.celery_task_id = celery_task.id
        db.commit()

        logger.info("job_enqueued", job_id=str(job.id), task_id=celery_task.id)
        return job

    except Exception as exc:
        db.rollback()
        logger.error("enqueue_failed", job_type=job_type, error=str(exc))
        raise TaskEnqueueError(f"No se pudo encolar la tarea: {exc}") from exc

def get_job(db: Session, job_id: uuid.UUID) -> Job:
    """
    Recupera un job por su ID.

    **Args:**
        db: Sesión activa de SQLAlchemy.
        job_id: UUID del job a buscar.

    **Returns:**
        Instancia del Job encontrado.

    **Raises:**
        TaskNotFoundError: Si no existe un job con ese ID.
    """
    job = db.get(Job, job_id)
    if not job:
        raise TaskNotFoundError(f"Job no encontrado: {job_id}")
    return job

def update_job_status(
    db: Session,
    job_id: uuid.UUID,
    status: JobStatus,
    result: dict | None = None,
    error_message: str | None = None,
) -> Job:
    """
    Actualiza el estado de un job y opcionalmente su resultado o mensaje de error.

    **Args:**
        db: Sesión activa de SQLAlchemy.
        job_id: UUID del job a actualizar.
        status: Nuevo estado del job.
        result: Diccionario con el resultado si la tarea fue exitosa.
        error_message: Descripción del error si la tarea falló.

    **Returns:**
        Instancia del Job con el estado actualizado.

    **Raises:**
        TaskNotFoundError: Si no existe un job con ese ID.
    """
    job = get_job(db, job_id)
    job.status = status

    if result is not None:
        job.result = result
    if error_message is not None:
        job.error_message = error_message

    db.commit()
    logger.info("job_status_updated", job_id=str(job_id), new_status=status)
    return job