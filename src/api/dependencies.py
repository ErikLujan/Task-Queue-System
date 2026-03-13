from fastapi import Header, HTTPException, status
from src.core.config import settings


def verify_host(host: str = Header(...)) -> str:
    """
    Valida que el header Host pertenezca a los hosts permitidos.

    **Args:**
        host: Header Host del request entrante.

    **Returns:**
        El mismo host si es válido.

    **Raises:**
        HTTPException 400: Si el host no está en la lista de permitidos.
    """
    hostname = host.split(":")[0]
    if hostname not in settings.allowed_hosts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Host no permitido.",
        )
    return host