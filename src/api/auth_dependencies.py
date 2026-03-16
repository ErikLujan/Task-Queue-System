from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.core.auth import decode_token
from src.core.database import get_db
from src.core.exceptions import SecurityError
from src.models.user import User, UserRole

_bearer = HTTPBearer()

def _get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    Extrae y valida el access token del header Authorization.
    Retorna el usuario autenticado si el token es válido.

    **Args:**
        credentials: Token extraído del header Authorization.
        db: Sesión activa de SQLAlchemy.

    **Returns:**
        Instancia del usuario autenticado.

    **Raises:**
        HTTPException 401: Si el token es inválido, expirado o revocado.
        HTTPException 403: Si el usuario está inactivo.
    """
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except SecurityError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    user = db.get(User, payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo.")

    return user

def require_user(user: User = Depends(_get_current_user)) -> User:
    """
    Dependencia que permite acceso a cualquier usuario autenticado.

    **Args:**
        user: Usuario autenticado inyectado por _get_current_user.

    **Returns:**
        El mismo usuario si está autenticado.
    """
    return user

def require_admin(user: User = Depends(_get_current_user)) -> User:
    """
    Dependencia que restringe el acceso exclusivamente a usuarios con rol admin.

    **Args:**
        user: Usuario autenticado inyectado por _get_current_user.

    **Returns:**
        El mismo usuario si tiene rol admin.

    **Raises:**
        HTTPException 403: Si el usuario no tiene rol admin.
    """
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol admin para esta operación.",
        )
    return user