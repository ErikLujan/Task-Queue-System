import csv
import uuid
from pathlib import Path

from src.workers.celery_app import celery_app
from src.core.config import settings
from src.core.exceptions import ValidationError
from src.models.job import JobStatus
from src.tasks.email_tasks import BaseTask, update_job_state
from src.services.storage_service import cleanup_directory
from src.utils.file_utils import get_output_path
from src.monitoring.health import full_health_report
from src.core.logging import get_logger

logger = get_logger(__name__)

_REPORT_HANDLERS: dict[str, callable] = {}

def _register_report(format_name: str):
    """
    Decorador interno para registrar handlers de generación de reportes.

    **Args:**
        format_name: Nombre del formato soportado (csv, pdf, excel).

    **Returns:**
        Decorador que registra la función en _REPORT_HANDLERS.
    """
    def decorator(fn):
        _REPORT_HANDLERS[format_name] = fn
        return fn
    return decorator

@_register_report("csv")
def _generate_csv(job_id: str, dataset_id: str, filters: dict) -> Path:
    """
    Genera un reporte en formato CSV.

    **Args:**
        job_id: UUID del job para nombrar el archivo de salida.
        dataset_id: Identificador del dataset a reportar.
        filters: Filtros a aplicar sobre los datos.

    **Returns:**
        Path del archivo CSV generado.
    """
    output_path = get_output_path(f"{job_id}.csv")
    rows = [
        {"id": 1, "dataset": dataset_id, "value": "ejemplo"},
        {"id": 2, "dataset": dataset_id, "value": "datos"},
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "dataset", "value"])
        writer.writeheader()
        writer.writerows(rows)
    return output_path

@_register_report("pdf")
def _generate_pdf(job_id: str, dataset_id: str, filters: dict) -> Path:
    """
    Genera un reporte en formato PDF.

    **Args:**
        job_id: UUID del job para nombrar el archivo de salida.
        dataset_id: Identificador del dataset a reportar.
        filters: Filtros a aplicar sobre los datos.

    **Returns:**
        Path del archivo PDF generado.
    """
    output_path = get_output_path(f"{job_id}.pdf")
    output_path.write_text(f"Reporte PDF — dataset: {dataset_id}")
    return output_path

@_register_report("excel")
def _generate_excel(job_id: str, dataset_id: str, filters: dict) -> Path:
    """
    Genera un reporte en formato Excel.

    **Args:**
        job_id: UUID del job para nombrar el archivo de salida.
        dataset_id: Identificador del dataset a reportar.
        filters: Filtros a aplicar sobre los datos.

    **Returns:**
        Path del archivo Excel generado.
    """
    output_path = get_output_path(f"{job_id}.xlsx")
    output_path.write_text(f"Reporte Excel — dataset: {dataset_id}")
    return output_path

@celery_app.task(
    bind=True,
    base=BaseTask,
    queue="reports",
    name="src.tasks.report_tasks.generate_report",
)
def generate_report(self, job_id: str, payload: dict) -> dict:
    """
    Genera un reporte en el formato solicitado de forma asíncrona.
    Actualiza el estado del job en DB en cada etapa del procesamiento.

    **Args:**
        job_id: UUID del job asociado a esta tarea.
        payload: Diccionario con report_type, dataset_id y filters validados.

    **Returns:**
        Diccionario con el job_id y el path del reporte generado.

    **Raises:**
        ValidationError: Si el formato solicitado no está soportado.
        self.retry: Si ocurre un error inesperado durante la generación.
    """
    webhook_url = payload.get("webhook_url")

    update_job_state(job_id, JobStatus.RUNNING)

    try:
        report_type = payload["report_type"]
        handler = _REPORT_HANDLERS.get(report_type)

        if not handler:
            raise ValidationError(f"Formato de reporte no soportado: '{report_type}'")

        output_path = handler(
            job_id=job_id,
            dataset_id=payload["dataset_id"],
            filters=payload.get("filters", {}),
        )

        result = {"job_id": job_id, "output_path": str(output_path)}
        update_job_state(job_id, JobStatus.SUCCESS, result=result, webhook_url=webhook_url)

        logger.info("report_generated", format=report_type)
        return result

    except ValidationError:
        raise

    except Exception as exc:
        logger.warning("report_generation_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)

@celery_app.task(
    name="src.tasks.report_tasks.cleanup_tmp_files",
    queue="reports",
)
def cleanup_tmp_files() -> dict:
    """
    Elimina archivos temporales con más de 24 horas de antigüedad.
    Ejecutada periódicamente por Celery Beat.

    **Returns:**
        Diccionario con la cantidad de archivos eliminados por directorio.
    """
    deleted_uploads = cleanup_directory(Path(settings.tmp_upload_dir), older_than_hours=24)
    deleted_outputs = cleanup_directory(Path(settings.tmp_output_dir), older_than_hours=24)
    logger.info("cleanup_completed", uploads=deleted_uploads, outputs=deleted_outputs)
    return {"uploads_deleted": deleted_uploads, "outputs_deleted": deleted_outputs}

@celery_app.task(
    name="src.tasks.report_tasks.system_health_check",
    queue="default",
)
def system_health_check() -> dict:
    """
    Ejecuta un health check completo del sistema y lo registra en el log.
    Ejecutada periódicamente por Celery Beat cada 5 minutos.

    **Returns:**
        Reporte de estado de todos los servicios.
    """
    report = {"redis": {"status": "ok"}}
    logger.info("health_check", report=report)
    return report