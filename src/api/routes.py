import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.exceptions import TaskEnqueueError, TaskNotFoundError, SecurityError, ValidationError
from src.core.logging import get_logger
from src.core.rate_limiter import limiter
from src.models.job import JobType
from src.schemas.job import JobResponse, JobDetailResponse
from src.schemas.task_payload import EmailTaskPayload, ImageTaskPayload, ReportTaskPayload
from src.services.queue_service import enqueue_job, get_job
from src.utils.validators import validate_uuid
from src.api.dependencies import verify_host

logger = get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])

def _handle_enqueue(db: Session, job_type: JobType, payload) -> JobResponse:
    """
    Lógica común de encolado compartida por todos los endpoints de creación.

    **Args:**
        db: Sesión activa de SQLAlchemy.
        job_type: Tipo de job a encolar.
        payload: Payload validado del job.

    **Returns:**
        Schema de respuesta con los datos del job creado.

    **Raises:**
        HTTPException 400: Si el payload contiene datos inválidos o inseguros.
        HTTPException 503: Si no se puede conectar con el broker de Celery.
    """
    try:
        job = enqueue_job(db, job_type, payload)
        return JobResponse.model_validate(job)
    except (ValidationError, SecurityError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except TaskEnqueueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.post(
    "/email",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Encolar tarea de envío de email",
)
@limiter.limit("10/minute")
def enqueue_email(
    request: Request,
    payload: EmailTaskPayload,
    db: Session = Depends(get_db),
    _host: str = Depends(verify_host),
) -> JobResponse:
    """
    Recibe un payload de email, lo valida y lo encola para procesamiento asíncrono.

    **Args:**
        request: Request HTTP — requerido por slowapi para identificar el cliente.
        payload: Datos del email a enviar (destinatario, asunto, cuerpo).
        db: Sesión de DB inyectada por FastAPI.

    **Returns:**
        Job creado con status 202 Accepted.
    """
    logger.info("email_job_requested", recipient=payload.recipient)
    return _handle_enqueue(db, JobType.EMAIL, payload)


@router.post(
    "/image",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Encolar tarea de procesamiento de imagen",
)
@limiter.limit("20/minute")
def enqueue_image(
    request: Request,
    payload: ImageTaskPayload,
    db: Session = Depends(get_db),
    _host: str = Depends(verify_host),
) -> JobResponse:
    """
    Recibe un payload de imagen, lo valida y lo encola para procesamiento asíncrono.

    **Args:**
        request: Request HTTP — requerido por slowapi para identificar el cliente.
        payload: Datos de la imagen a procesar (nombre, operaciones, formato).
        db: Sesión de DB inyectada por FastAPI.

    **Returns:**
        Job creado con status 202 Accepted.
    """
    logger.info("image_job_requested", filename=payload.filename)
    return _handle_enqueue(db, JobType.IMAGE, payload)


@router.post(
    "/report",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Encolar tarea de generación de reporte",
)
@limiter.limit("5/minute")
def enqueue_report(
    request: Request,
    payload: ReportTaskPayload,
    db: Session = Depends(get_db),
    _host: str = Depends(verify_host),
) -> JobResponse:
    """
    Recibe un payload de reporte, lo valida y lo encola para procesamiento asíncrono.

    **Args:**
        request: Request HTTP — requerido por slowapi para identificar el cliente.
        payload: Datos del reporte a generar (tipo, dataset, filtros).
        db: Sesión de DB inyectada por FastAPI.

    **Returns:**
        Job creado con status 202 Accepted.
    """
    logger.info("report_job_requested", dataset_id=payload.dataset_id)
    return _handle_enqueue(db, JobType.REPORT, payload)


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Consultar estado de un job",
)
@limiter.limit("60/minute")
def get_job_status(
    request: Request,
    job_id: str,
    db: Session = Depends(get_db),
    _host: str = Depends(verify_host),
) -> JobResponse:
    """
    Retorna el estado actual de un job dado su ID.

    **Args:**
        request: Request HTTP — requerido por slowapi para identificar el cliente.
        job_id: UUID del job a consultar.
        db: Sesión de DB inyectada por FastAPI.

    **Returns:**
        Job con su estado actual.

    **Raises:**
        HTTPException 400: Si el job_id no tiene formato UUID válido.
        HTTPException 404: Si no existe un job con ese ID.
    """
    try:
        validated_id = validate_uuid(job_id)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    try:
        job = get_job(db, validated_id)
        return JobResponse.model_validate(job)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/{job_id}/detail",
    response_model=JobDetailResponse,
    summary="Consultar detalle completo de un job",
)
@limiter.limit("30/minute")
def get_job_detail(
    request: Request,
    job_id: str,
    db: Session = Depends(get_db),
    _host: str = Depends(verify_host),
) -> JobDetailResponse:
    """
    Retorna el detalle completo de un job incluyendo payload y resultado.
    Endpoint de uso interno — expone más información que el endpoint de estado.

    **Args:**
        request: Request HTTP — requerido por slowapi para identificar el cliente.
        job_id: UUID del job a consultar.
        db: Sesión de DB inyectada por FastAPI.

    **Returns:**
        Job con payload, resultado y estado completo.

    **Raises:**
        HTTPException 400: Si el job_id no tiene formato UUID válido.
        HTTPException 404: Si no existe un job con ese ID.
    """
    try:
        validated_id = validate_uuid(job_id)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    try:
        job = get_job(db, validated_id)
        return JobDetailResponse.model_validate(job)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))