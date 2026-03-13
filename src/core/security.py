import re
import os
import hashlib
import mimetypes
from pathlib import Path

from src.core.config import settings
from src.core.exceptions import SecurityError, ValidationError
from src.core.logging import get_logger

logger = get_logger(__name__)

# Patrones de ataque conocidos
_SQL_INJECTION_PATTERN = re.compile(
    r"(--|;|'|\"|\/\*|\*\/|xp_|UNION|SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|EXEC|CAST|CONVERT)",
    re.IGNORECASE,
)
_PATH_TRAVERSAL_PATTERN = re.compile(r"\.\.[/\\]")
_NULL_BYTE_PATTERN = re.compile(r"\x00")

def sanitize_string(value: str, field_name: str = "input") -> str:
    """
    Sanitiza un string detectando patrones de inyección SQL, path traversal y null bytes.

    **Args**:
        value: String a validar.
        field_name: Nombre del campo para mensajes de error descriptivos.

    **Returns**:
        El mismo string si es seguro.

    **Raises**:
        SecurityError: Si se detecta un patrón malicioso.
    """
    if _NULL_BYTE_PATTERN.search(value):
        logger.warning("null_byte_detected", field=field_name)
        raise SecurityError(f"Input inválido en campo '{field_name}'.")

    if _PATH_TRAVERSAL_PATTERN.search(value):
        logger.warning("path_traversal_detected", field=field_name)
        raise SecurityError(f"Input inválido en campo '{field_name}'.")

    if _SQL_INJECTION_PATTERN.search(value):
        logger.warning("sql_injection_attempt", field=field_name, value_preview=value[:30])
        raise SecurityError(f"Input inválido en campo '{field_name}'.")

    return value

def validate_file(file_path: Path, expected_content_types: list[str]) -> None:
    """
    Valida tamaño, tipo MIME real y que el path no salga del directorio permitido.

    **Args**:
        file_path: Path absoluto del archivo a validar.
        expected_content_types: Lista de MIME types permitidos (e.g. ["image/jpeg"]).

    **Raises**:
        ValidationError: Si el archivo excede el tamaño o el tipo no está permitido.
        SecurityError: Si el path intenta salir del directorio base.
    """
    resolved = file_path.resolve()
    base_dir = Path(settings.tmp_upload_dir).resolve()

    if not str(resolved).startswith(str(base_dir)):
        logger.warning("path_escape_attempt", path=str(file_path))
        raise SecurityError("Acceso a path no permitido.")

    if not resolved.exists():
        raise ValidationError(f"El archivo no existe: {file_path.name}")

    size = resolved.stat().st_size
    if size > settings.max_file_size_bytes:
        raise ValidationError(
            f"El archivo supera el límite de {settings.max_file_size_mb}MB "
            f"(tamaño recibido: {size / 1024 / 1024:.2f}MB)."
        )

    detected_type, _ = mimetypes.guess_type(str(resolved))
    if detected_type not in expected_content_types:
        raise ValidationError(
            f"Tipo de archivo no permitido: '{detected_type}'. "
            f"Permitidos: {expected_content_types}"
        )

def secure_filename(filename: str) -> str:
    """
    Genera un nombre de archivo seguro eliminando caracteres peligrosos
    y añadiendo un hash para evitar colisiones y enumeración.

    **Args**:
        filename: Nombre original del archivo.

    **Returns**:
        Nombre sanitizado con hash único.

    **Raises**:
        ValidationError: Si el nombre resultante queda vacío tras la sanitización.
    """
    name = Path(filename)
    stem = re.sub(r"[^\w\-]", "_", name.stem)
    suffix = re.sub(r"[^\w]", "", name.suffix.lower())

    stem = re.sub(r"_+", "_", stem).strip("_")

    if not stem:
        raise ValidationError("El nombre del archivo es inválido.")

    unique_hash = hashlib.sha1(os.urandom(16)).hexdigest()[:8]
    return f"{stem}_{unique_hash}.{suffix}"