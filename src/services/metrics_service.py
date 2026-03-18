from sqlalchemy.orm import Session
from src.core.metrics import JOBS_BY_STATUS, JOB_ERRORS_TOTAL, JOB_RETRIES_TOTAL
from src.core.logging import get_logger
from src.models.job import JobStatus

logger = get_logger(__name__)

def refresh_job_status_metrics(db: Session) -> None:
    """
    Consulta la DB y actualiza los gauges de jobs por estado.
    Se llama periódicamente desde Celery Beat para mantener los datos frescos.

    **Args:**
        db: Sesión activa de SQLAlchemy.
    """
    from src.models.job import Job
    from sqlalchemy import func

    try:
        results = (
            db.query(Job.status, func.count(Job.id))
            .group_by(Job.status)
            .all()
        )

        # Casos exitosos (status = "success")
        for status in JobStatus:
            JOBS_BY_STATUS.labels(status=status.value).set(0)

        for status, count in results:
            JOBS_BY_STATUS.labels(status=status).set(count)

        # Casos de jos erroneas (status = "failure")
        error_count = (
            db.query(func.count(Job.id))
            .filter(Job.status == JobStatus.FAILURE.value)
            .scalar() or 0
        )
        JOB_ERRORS_TOTAL.labels(job_type="all")._value.set(error_count)

        # Casos en los que hay reintentos (status = "retrying")
        retry_count = (
            db.query(func.sum(Job.retry_count))
            .scalar() or 0
        )
        JOB_RETRIES_TOTAL.labels(job_type="all")._value.set(retry_count)

        logger.debug("job_status_metrics_refreshed")

    except Exception as exc:
        logger.warning("job_status_metrics_failed", error=str(exc))