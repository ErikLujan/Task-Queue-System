import re
import uuid

from src.core.exceptions import ValidationError

_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

def validate_uuid(value: str) -> uuid.UUID:
    """
    Valida y convierte un string a UUID v4.

    **Args:**
        value: String a validar como UUID.

    **Returns:**
        Instancia de uuid.UUID si el formato es válido.

    **Raises:**
        ValidationError: Si el string no tiene formato UUID v4 válido.
    """
    if not _UUID_PATTERN.match(value):
        raise ValidationError(f"Formato de UUID inválido: '{value}'")
    return uuid.UUID(value)

def validate_pagination(page: int, page_size: int) -> tuple[int, int]:
    """
    Valida y normaliza parámetros de paginación para evitar queries abusivos.

    **Args:**
        page: Número de página solicitado (base 1).
        page_size: Cantidad de resultados por página.

    **Returns:**
        Tupla (page, page_size) validada y normalizada.

    **Raises:**
        ValidationError: Si los valores están fuera de rango.
    """
    if page < 1:
        raise ValidationError("El número de página debe ser mayor a 0.")
    if not (1 <= page_size <= 100):
        raise ValidationError("El tamaño de página debe estar entre 1 y 100.")
    return page, page_size