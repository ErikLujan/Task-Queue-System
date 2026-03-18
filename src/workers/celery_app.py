from celery import Celery
from celery.schedules import crontab
from celery.app.routes import Router
from kombu import Queue
from celery.signals import task_prerun, task_postrun, task_failure
from celery.utils.log import get_task_logger

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)
task_logger = get_task_logger(__name__)

def create_celery_app() -> Celery:
    """
    Crea y configura la instancia de Celery con todas las políticas de seguridad,
    límites de tiempo y rutas de tareas.

    **Returns:**
        Instancia de Celery lista para usar.
    """
    app = Celery("task_queue_system")

    app.conf.update(
        # Broker y backend
        broker_url=str(settings.redis_url),
        result_backend=str(settings.redis_url),
        broker_connection_retry_on_startup=True,
        broker_pool_limit=settings.redis_max_connections,

        # Serialización — solo JSON, nunca pickle
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        event_serializer="json",

        # Límites de tiempo
        task_soft_time_limit=settings.celery_task_soft_time_limit,
        task_time_limit=settings.celery_task_hard_time_limit,

        # Reintentos y acknowledgment
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_max_retries=settings.celery_task_max_retries,

        # Rutas por tipo de tarea
        task_routes={
            "src.tasks.email_tasks.*":  {"queue": "emails"},
            "src.tasks.image_tasks.*":  {"queue": "images"},
            "src.tasks.report_tasks.*": {"queue": "reports"},
        },

        # Colas declaradas correctamente como objetos Queue
        task_default_queue="default",
        task_queues=(
            Queue("default"),
            Queue("emails"),
            Queue("images"),
            Queue("reports"),
        ),

        # Timezone
        timezone="UTC",
        enable_utc=True,

        # Autodiscovery
        include=[
            "src.tasks.email_tasks",
            "src.tasks.image_tasks",
            "src.tasks.report_tasks",
        ],
    )

    return app

celery_app = create_celery_app()

celery_app.conf.beat_schedule = {

    "cleanup-tmp-files-daily": {
        "task": "src.tasks.report_tasks.cleanup_tmp_files",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "reports"},
    },

    "health-check-every-five-minutes": {
        "task": "src.tasks.report_tasks.system_health_check",
        "schedule": crontab(minute="*/5"),
        "options": {"queue": "default"},
    },

    "refresh-job-status-metrics": {
        "task": "src.tasks.report_tasks.refresh_metrics",
        "schedule": crontab(minute="*/1"),
        "options": {"queue": "default"},
    },
}

# ---------------------------------------------------------------------------
# Signals — hooks del ciclo de vida de cada tarea
# ---------------------------------------------------------------------------

@task_prerun.connect
def on_task_start(task_id: str, task, *args, **kwargs) -> None:
    """
    Se ejecuta justo antes de que una tarea comience a procesarse.

    **Args:**
        task_id: ID único de la tarea asignado por Celery.
        task: Instancia de la tarea que va a ejecutarse.
    """
    logger.info("task_started", task_id=task_id, task_name=task.name)

@task_postrun.connect
def on_task_complete(task_id: str, task, retval, state: str, *args, **kwargs) -> None:
    """
    Se ejecuta después de que una tarea finaliza, sin importar el resultado.

    **Args:**
        task_id: ID único de la tarea.
        task: Instancia de la tarea ejecutada.
        retval: Valor de retorno de la tarea.
        state: Estado final de la tarea (SUCCESS, FAILURE, etc.).
    """
    logger.info("task_finished", task_id=task_id, task_name=task.name, state=state)

@task_failure.connect
def on_task_failure(task_id: str, exception: Exception, traceback, *args, **kwargs) -> None:
    """
    Se ejecuta cuando una tarea falla de forma definitiva (cuando agota sus reintentos).

    **Args:**
        task_id: ID único de la tarea fallida.
        exception: Excepción que causó el fallo.
        traceback: Traceback completo del error.
    """
    logger.error(
        "task_failed_permanently",
        task_id=task_id,
        error=str(exception),
        exc_info=True,
    )