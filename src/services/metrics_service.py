from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from src.core.metrics import JOBS_BY_STATUS, JOB_ERRORS_TOTAL, JOB_RETRIES_TOTAL
from src.core.logging import get_logger
from src.models.job import Job, JobStatus

logger = get_logger(__name__)


async def refresh_job_status_metrics(db: AsyncSession) -> None:
    """
    Consulta la DB y actualiza los gauges de jobs por estado.
    Se llama periódicamente desde Celery Beat para mantener los datos frescos.

    **Args:**
        db: Sesión activa de SQLAlchemy AsyncSession.
    """
    try:
        result = await db.execute(
            select(Job.status, func.count(Job.id)).group_by(Job.status)
        )
        results = result.all()

        # Casos exitosos (status = "success")
        for status in JobStatus:
            JOBS_BY_STATUS.labels(status=status.value).set(0)

        for status, count in results:
            JOBS_BY_STATUS.labels(status=status).set(count)

        # Casos de jobs erroneas (status = "failure")
        error_result = await db.execute(
            select(func.count(Job.id)).where(Job.status == JobStatus.FAILURE.value)
        )
        error_count = error_result.scalar() or 0
        JOB_ERRORS_TOTAL.labels(job_type="all")._value.set(error_count)

        # Casos en los que hay reintentos (status = "retrying")
        retry_result = await db.execute(select(func.sum(Job.retry_count)))
        retry_count = retry_result.scalar() or 0
        JOB_RETRIES_TOTAL.labels(job_type="all")._value.set(retry_count)

        logger.debug("job_status_metrics_refreshed")

    except Exception as exc:
        logger.warning("job_status_metrics_failed", error=str(exc))
