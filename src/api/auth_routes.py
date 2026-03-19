from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.auth import decode_token, revoke_token
from src.core.database import get_db
from src.core.exceptions import ValidationError, SecurityError
from src.core.logging import get_logger
from src.core.rate_limiter import limiter
from src.schemas.auth import LoginRequest, RegisterRequest, RefreshRequest, TokenResponse, UserResponse
from src.services.auth_service import login_user, logout_user, refresh_tokens, register_user
from src.services.audit_service import log_action
from src.api.dependencies import verify_host
from src.api.auth_dependencies import require_user
from src.models.user import User

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer()

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo usuario",
)
@limiter.limit("5/minute")
def register(
    request: Request,
    data: RegisterRequest,
    db: Session = Depends(get_db),
    _host: str = Depends(verify_host),
) -> UserResponse:
    """
    Registra un nuevo usuario en el sistema con rol user por defecto.

    **Args:**
        request: Request HTTP — requerido por slowapi.
        data: Email y contraseña del nuevo usuario.
        db: Sesión de DB inyectada por FastAPI.

    **Returns:**
        Datos públicos del usuario creado.

    **Raises:**
        HTTPException 400: Si el email ya está registrado.
    """
    try:
        user = register_user(db, data)

        log_action(
            db=db,
            action="register",
            resource="user",
            resource_id=str(user.id),
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
        )

        return UserResponse(
            id=str(user.id),
            email=user.email,
            role=user.role,
            is_active=user.is_active,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión",
)
@limiter.limit("10/minute")
def login(
    request: Request,
    data: LoginRequest,
    db: Session = Depends(get_db),
    _host: str = Depends(verify_host),
) -> TokenResponse:
    """
    Autentica un usuario y retorna un par de tokens JWT.

    **Args:**
        request: Request HTTP — requerido por slowapi.
        data: Credenciales del usuario.
        db: Sesión de DB inyectada por FastAPI.

    **Returns:**
        Access token y refresh token.

    **Raises:**
        HTTPException 401: Si las credenciales son incorrectas.
    """
    try:
        result = login_user(db, data)

        log_action(
            db=db,
            action="login",
            resource="user",
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
        )

        return result
    except SecurityError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cerrar sesión",
)
@limiter.limit("10/minute")
def logout(
    request: Request,
    data: RefreshRequest,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
    _host: str = Depends(verify_host),
) -> None:
    """
    Revoca el access token y el refresh token, invalidando la sesión completamente.

    **Args:**
        request: Request HTTP — requerido por slowapi.
        data: Refresh token a revocar.
        credentials: Access token extraído del header Authorization.
        db: Sesión de DB inyectada por FastAPI.

    **Returns:**
        204 No Content si el logout fue exitoso.
    """
    logout_user(credentials.credentials, data.refresh_token)

    log_action(
        db=db,
        action="logout",
        resource="user",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
    )

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refrescar access token",
)
@limiter.limit("10/minute")
def refresh(
    request: Request,
    data: RefreshRequest,
    _host: str = Depends(verify_host),
) -> TokenResponse:
    """
    Genera un nuevo par de tokens a partir de un refresh token válido.
    El refresh token usado queda revocado — rotación automática.

    **Args:**
        request: Request HTTP — requerido por slowapi.
        data: Refresh token vigente.

    **Returns:**
        Nuevo par de tokens access y refresh.

    **Raises:**
        HTTPException 401: Si el refresh token es inválido o expirado.
    """
    try:
        return refresh_tokens(data.refresh_token)
    except SecurityError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Obtener datos del usuario autenticado",
)
@limiter.limit("60/minute")
def me(request: Request, current_user: User = Depends(require_user)) -> UserResponse:
    """
    Retorna los datos del usuario autenticado a partir de su access token.

    **Args:**
        current_user: Usuario autenticado inyectado por la dependencia require_user.

    **Returns:**
        Datos públicos del usuario autenticado.
    """
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
    )