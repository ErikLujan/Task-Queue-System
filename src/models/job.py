import uuid

from enum import Enum
from sqlalchemy import String, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class JobStatus(str, Enum):
    """
    Estados posibles de un job a lo largo de su ciclo de vida.
    """
    PENDING  = "pending"
    RUNNING  = "running"
    SUCCESS  = "success"
    FAILURE  = "failure"
    RETRYING = "retrying"
    REVOKED  = "revoked"


class JobType(str, Enum):
    """
    Tipos de tarea soportados por el sistema.
    """
    EMAIL  = "email"
    IMAGE  = "image"
    REPORT = "report"


class Job(Base, TimestampMixin):
    """
    Representa un job encolado en el sistema.
    Registra el ciclo de vida completo de cada tarea procesada.
    """

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(155), unique=True, index=True)
    job_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=JobStatus.PENDING, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<Job id={self.id} type={self.job_type} status={self.status}>"