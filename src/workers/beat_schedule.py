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
            "schedule": crontab(hour=3, minute=0),   # --> Todos los días a las 3 AM UTC
            "options": {"queue": "reports"},
        },

        "health-check-every-minute": {
            "task": "src.tasks.report_tasks.system_health_check",
            "schedule": crontab(minute="*/5"),        # --> Cada 5 minutos
            "options": {"queue": "default"},
        },
    }

register_beat_schedule()