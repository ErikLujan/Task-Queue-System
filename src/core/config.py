from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, RedisDsn, PostgresDsn

class Settings(BaseSettings):
    """Configuración central de la aplicación cargada desde variables de entorno."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "Task Queue System"
    environment: str = Field(default="development", pattern="^(development|staging|production)$")
    debug: bool = False

    # Redis
    redis_url: RedisDsn
    redis_password: str = Field(min_length=1)
    redis_max_connections: int = 20

    # PostgreSQL
    database_url: PostgresDsn
    db_user: str = Field(min_length=1)
    db_password: str = Field(min_length=1)
    db_name: str = Field(min_length=1)
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Celery
    celery_task_max_retries: int = 3
    celery_task_soft_time_limit: int = 300
    celery_task_hard_time_limit: int = 600

    # Archivos
    max_file_size_mb: int = Field(default=10, ge=1, le=100)
    allowed_image_types: list[str] = ["image/jpeg", "image/png", "image/webp"]
    tmp_upload_dir: str = "tmp/uploads"
    tmp_output_dir: str = "tmp/outputs"

    # Seguridad
    secret_key: str = Field(min_length=32)
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]

    # Flower
    flower_user: str = Field(min_length=1)
    flower_password: str = Field(min_length=1)

    # Grafana
    grafana_user: str = Field(min_length=1)
    grafana_password: str = Field(min_length=1)

    @property
    def max_file_size_bytes(self) -> int:
        """Retorna el tamaño máximo de archivo en bytes."""
        return self.max_file_size_mb * 1024 * 1024

settings = Settings()