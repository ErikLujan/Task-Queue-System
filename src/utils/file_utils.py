from pathlib import Path
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

def ensure_tmp_dirs() -> None:
    """
    Crea los directorios temporales necesarios si no existen.
    Se llama al iniciar la aplicación.
    """
    for dir_path in [settings.tmp_upload_dir, settings.tmp_output_dir]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        logger.debug("tmp_dir_ready", path=dir_path)

def get_output_path(filename: str) -> Path:
    """
    Construye el path de salida para un archivo procesado.

    **Args:**
        filename: Nombre del archivo de salida.

    **Returns:**
        Path completo dentro del directorio de outputs.
    """
    return Path(settings.tmp_output_dir) / filename