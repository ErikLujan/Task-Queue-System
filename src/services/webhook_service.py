import httpx
from src.core.logging import get_logger

logger = get_logger(__name__)

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

_MAX_RETRIES = 3


def dispatch_webhook(webhook_url: str, payload: dict) -> None:
    """
    Envía una notificación HTTP POST a la URL indicada con el resultado del job.
    Reintenta hasta 3 veces ante errores de red o timeouts.
    No lanza excepciones — un fallo en el webhook no debe afectar al job.

    **Args:**
        webhook_url: URL destino del webhook.
        payload: Diccionario con los datos del job a notificar.
    """
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                response = client.post(webhook_url, json=payload)
                response.raise_for_status()
                logger.info(
                    "webhook_dispatched",
                    url=webhook_url,
                    status_code=response.status_code,
                    attempt=attempt,
                )
                return

        except httpx.TimeoutException:
            logger.warning("webhook_timeout", url=webhook_url, attempt=attempt)

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "webhook_http_error",
                url=webhook_url,
                status_code=exc.response.status_code,
                attempt=attempt,
            )
            if exc.response.status_code < 500:
                return

        except Exception as exc:
            logger.warning("webhook_failed", url=webhook_url, error=str(exc), attempt=attempt)

    logger.error("webhook_exhausted", url=webhook_url, max_retries=_MAX_RETRIES)