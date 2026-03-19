from pydantic import BaseModel, EmailStr, Field, AnyHttpUrl, field_validator, model_validator, model_serializer
from typing import Optional
from src.core.security import sanitize_string

class BasePayload(BaseModel):
    """
    Schema base del que heredan todos los payloads. Aplica sanitización común.
    """

    model_config = {"str_strip_whitespace": True, "frozen": True}

    webhook_url: Optional[AnyHttpUrl] = None # --> URL Opcional para las notificaciones
    priority: int = Field(default=5, ge=0, le=9)  # --> 0 = más alta, 9 = más baja

    @model_validator(mode="before")
    @classmethod
    def sanitize_string_fields(cls, values: dict) -> dict:
        """
        Sanitiza todos los campos string antes de la validación de tipos.

        **Raises:**
            SecurityError: Si algún campo contiene patrones maliciosos.
        """
        return {
            k: sanitize_string(v, field_name=k) if isinstance(v, str) else v
            for k, v in values.items()
        }
    
    def model_dump(self, **kwargs) -> dict:
        """
        Sobreescribe model_dump para convertir AnyHttpUrl a string plano
        antes de serializar — necesario para guardar en JSONB de PostgreSQL.

        **Returns:**
            Diccionario con todos los valores serializables a JSON.
        """
        data = super().model_dump(**kwargs)
        if data.get("webhook_url") is not None:
            data["webhook_url"] = str(data["webhook_url"])
        return data

class EmailTaskPayload(BasePayload):
    """
    Payload para tareas de envío de email.
    """

    recipient: EmailStr
    subject: str = Field(min_length=1, max_length=150)
    body: str = Field(min_length=1, max_length=5000)
    retry_on_failure: bool = True

class ImageTaskPayload(BasePayload):
    """
    Payload para tareas de procesamiento de imágenes.
    """

    filename: str = Field(min_length=1, max_length=255)
    operations: list[str] = Field(min_length=1, max_length=5)
    output_format: str = Field(default="jpeg", pattern="^(jpeg|png|webp)$")

    @field_validator("operations")
    @classmethod
    def validate_operations(cls, ops: list[str]) -> list[str]:
        """
        Valida que las operaciones solicitadas estén en la whitelist permitida.

        **Args:**
            ops: Lista de operaciones a aplicar sobre la imagen.

        **Returns:**
            La misma lista si todas las operaciones son válidas.

        **Raises:**
            ValueError: Si alguna operación no está en la whitelist.
        """
        allowed = {"resize", "grayscale", "rotate", "flip", "compress"}
        invalid = set(ops) - allowed
        if invalid:
            raise ValueError(f"Operaciones no permitidas: {invalid}. Permitidas: {allowed}")
        return ops

class ReportTaskPayload(BasePayload):
    """
    Payload para tareas de generación de reportes.
    """

    report_type: str = Field(pattern="^(csv|pdf|excel)$")
    dataset_id: str = Field(min_length=1, max_length=100)
    filters: dict = Field(default_factory=dict, max_length=10)

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, filters: dict) -> dict:
        """
        Valida que los filtros no contengan claves o valores sospechosos.

        **Args:**
            filters: Diccionario de filtros a aplicar en el reporte.

        **Returns:**
            El mismo diccionario si pasa la validación.

        **Raises:**
            ValueError: Si alguna clave o valor contiene caracteres no permitidos.
        """
        allowed_key_pattern = __import__("re").compile(r"^[a-zA-Z0-9_]{1,50}$")
        for key, value in filters.items():
            if not allowed_key_pattern.match(key):
                raise ValueError(f"Clave de filtro inválida: '{key}'")
            if isinstance(value, str) and len(value) > 200:
                raise ValueError(f"Valor del filtro '{key}' excede 200 caracteres.")
        return filters