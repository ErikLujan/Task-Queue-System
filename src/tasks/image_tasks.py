from pathlib import Path

from PIL import Image, UnidentifiedImageError

from src.workers.celery_app import celery_app
from src.core.config import settings
from src.core.exceptions import ValidationError, StorageError
from src.core.security import validate_file
from src.models.job import JobStatus
from src.tasks.email_tasks import BaseTask, update_job_state
from src.utils.file_utils import get_output_path
from src.core.logging import get_logger

logger = get_logger(__name__)

_MAX_IMAGE_PIXELS = 50_000_000
_OPERATION_HANDLERS: dict[str, callable] = {}

def _register_operation(name: str):
    """
    Decorador interno para registrar handlers de operaciones de imagen.

    **Args:**
        name: Nombre de la operación a registrar.

    **Returns:**
        Decorador que registra la función en _OPERATION_HANDLERS.
    """
    def decorator(fn):
        _OPERATION_HANDLERS[name] = fn
        return fn
    return decorator

@_register_operation("grayscale")
def _apply_grayscale(img: Image.Image, **_) -> Image.Image:
    """Convierte la imagen a escala de grises."""
    return img.convert("L")

@_register_operation("flip")
def _apply_flip(img: Image.Image, **_) -> Image.Image:
    """Voltea la imagen horizontalmente."""
    return img.transpose(Image.FLIP_LEFT_RIGHT)

@_register_operation("rotate")
def _apply_rotate(img: Image.Image, degrees: int = 90, **_) -> Image.Image:
    """
    Rota la imagen el número de grados indicado.

    **Args:**
        img: Imagen a rotar.
        degrees: Grados de rotación. Por defecto 90.

    **Returns:**
        Imagen rotada.
    """
    if degrees not in {90, 180, 270}:
        raise ValidationError("Rotación permitida: 90, 180 o 270 grados.")
    return img.rotate(degrees, expand=True)

@_register_operation("resize")
def _apply_resize(img: Image.Image, width: int = 800, height: int = 600, **_) -> Image.Image:
    """
    Redimensiona la imagen al tamaño indicado.

    **Args:**
        img: Imagen a redimensionar.
        width: Ancho destino en píxeles. Por defecto 800.
        height: Alto destino en píxeles. Por defecto 600.

    **Returns:**
        Imagen redimensionada.

    **Raises:**
        ValidationError: Si las dimensiones están fuera del rango permitido.
    """
    if not (1 <= width <= 4000) or not (1 <= height <= 4000):
        raise ValidationError("Dimensiones fuera del rango permitido (1–4000px).")
    return img.resize((width, height), Image.LANCZOS)

@_register_operation("compress")
def _apply_compress(img: Image.Image, **_) -> Image.Image:
    """Devuelve la imagen sin modificación — la compresión se aplica al guardar."""
    return img

@celery_app.task(
    bind=True,
    base=BaseTask,
    queue="images",
    name="src.tasks.image_tasks.process_image",
)
def process_image(self, job_id: str, payload: dict) -> dict:
    """
    Aplica una secuencia de operaciones sobre una imagen de forma asíncrona.
    Actualiza el estado del job en DB en cada etapa del procesamiento.

    **Args:**
        job_id: UUID del job asociado a esta tarea.
        payload: Diccionario con filename, operations y output_format validados.

    **Returns:**
        Diccionario con el job_id y el path del archivo resultante.

    **Raises:**
        ValidationError: Si el archivo no existe o las operaciones son inválidas.
        StorageError: Si no se puede guardar el resultado.
        self.retry: Si ocurre un error inesperado durante el procesamiento.
    """
    webhook_url = payload.get("webhook_url")

    update_job_state(job_id, JobStatus.RUNNING)

    try:
        source_path = Path(settings.tmp_upload_dir) / payload["filename"]
        validate_file(source_path, settings.allowed_image_types)

        Image.MAX_IMAGE_PIXELS = _MAX_IMAGE_PIXELS

        with Image.open(source_path) as img:
            processed = img.copy()

        for operation in payload["operations"]:
            handler = _OPERATION_HANDLERS.get(operation)
            if not handler:
                raise ValidationError(f"Operación desconocida: '{operation}'")
            processed = handler(processed)

        output_format = payload.get("output_format", "jpeg")
        output_path = get_output_path(f"{job_id}.{output_format}")

        save_kwargs = {"optimize": True}
        if output_format == "jpeg":
            save_kwargs["quality"] = 85

        processed.save(output_path, format=output_format.upper(), **save_kwargs)

        result = {"job_id": job_id, "output_path": str(output_path)}
        update_job_state(job_id, JobStatus.SUCCESS, result=result, webhook_url=webhook_url)

        logger.info("image_processed", output=str(output_path))
        return result

    except (ValidationError, UnidentifiedImageError) as exc:
        logger.error("image_processing_invalid", error=str(exc))
        raise

    except Exception as exc:
        logger.warning("image_processing_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)