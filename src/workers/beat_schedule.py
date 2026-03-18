from celery.schedules import crontab
from src.workers.celery_app import celery_app

def register_beat_schedule() -> None:
    """
    Registra todas las tareas periódicas en el scheduler de Celery Beat.
    Centraliza la configuración de schedules para evitar definiciones dispersas.
    """
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

register_beat_schedule()