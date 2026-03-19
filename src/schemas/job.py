import uuid

from datetime import datetime
from pydantic import BaseModel
from src.models.job import JobStatus, JobType

class JobResponse(BaseModel):
    """
    Schema de respuesta para exponer el estado de un job al cliente.
    """

    model_config = {"from_attributes": True}

    id: uuid.UUID
    celery_task_id: str | None
    job_type: JobType
    status: JobStatus
    priority: int
    retry_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime

class JobDetailResponse(JobResponse):
    """
    Schema extendido que incluye payload y resultado. Solo para uso interno/admin.
    """

    payload: dict
    result: dict | None