import shutil
from pathlib import Path

from src.core.config import settings
from src.core.exceptions import StorageError
from src.core.logging import get_logger
from src.core.security import secure_filename, validate_file

logger = get_logger(__name__)

def save_upload(source_path: Path, content_type: list[str]) -> Path:
    """
    Valida y mueve un archivo subido al directorio de uploads seguro.

    **Args:**
        source_path: Path temporal del archivo recibido.
        content_type: Lista de MIME types permitidos para este archivo.

    **Returns:**
        Path final donde quedó guardado el archivo.

    **Raises:**
        ValidationError: Si el archivo no pasa las validaciones de tamaño o tipo.
        SecurityError: Si el path intenta escapar del directorio permitido.
        StorageError: Si ocurre un error al mover el archivo.
    """
    validate_file(source_path, content_type)

    safe_name = secure_filename(source_path.name)
    dest_path = Path(settings.tmp_upload_dir) / safe_name

    try:
        shutil.move(str(source_path), dest_path)
        logger.info("file_saved", filename=safe_name)
        return dest_path
    except OSError as exc:
        raise StorageError(f"No se pudo guardar el archivo: {exc}") from exc

def delete_file(file_path: Path) -> None:
    """
    Elimina un archivo del sistema de forma segura, validando el path antes.

    **Args:**
        file_path: Path del archivo a eliminar.

    **Raises:**
        SecurityError: Si el path intenta salir del directorio base.
        StorageError: Si el archivo no se puede eliminar.
    """
    resolved = file_path.resolve()
    base_dirs = [
        Path(settings.tmp_upload_dir).resolve(),
        Path(settings.tmp_output_dir).resolve(),
    ]

    if not any(str(resolved).startswith(str(b)) for b in base_dirs):
        raise __import__("src.core.exceptions", fromlist=["SecurityError"]).SecurityError(
            "Intento de eliminar archivo fuera del directorio permitido."
        )

    try:
        resolved.unlink(missing_ok=True)
        logger.info("file_deleted", path=str(resolved))
    except OSError as exc:
        raise StorageError(f"No se pudo eliminar el archivo: {exc}") from exc

def cleanup_directory(directory: Path, older_than_hours: int = 24) -> int:
    """
    Elimina archivos de un directorio que superen cierta antigüedad.
    Usado por la tarea periódica de limpieza de temporales.

    **Args:**
        directory: Directorio a limpiar.
        older_than_hours: Antigüedad mínima en horas para eliminar un archivo.

    **Returns:**
        Cantidad de archivos eliminados.
    """
    import time

    cutoff = time.time() - (older_than_hours * 3600)
    deleted = 0

    for file in directory.iterdir():
        if file.is_file() and file.stat().st_mtime < cutoff:
            file.unlink(missing_ok=True)
            deleted += 1

    logger.info("cleanup_done", directory=str(directory), deleted=deleted)
    return deleted