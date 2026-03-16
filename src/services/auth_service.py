from sqlalchemy.orm import Session

from src.core.auth import hash_password, verify_password, create_token_pair, decode_token, revoke_token
from src.core.exceptions import ValidationError, SecurityError
from src.core.logging import get_logger
from src.models.user import User, UserRole
from src.schemas.auth import RegisterRequest, LoginRequest, TokenResponse

logger = get_logger(__name__)

def register_user(db: Session, data: RegisterRequest) -> User:
    """
    Registra un nuevo usuario validando que el email no esté en uso.

    **Args:**
        db: Sesión activa de SQLAlchemy.
        data: Payload de registro validado.

    **Returns:**
        Instancia del usuario creado.

    **Raises:**
        ValidationError: Si el email ya está registrado.
    """
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise ValidationError("El email ya está registrado.")

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info("user_registered", user_id=str(user.id), email=user.email)
    return user

def login_user(db: Session, data: LoginRequest) -> TokenResponse:
    """
    Autentica un usuario y retorna un par de tokens JWT.
    El mensaje de error es genérico para no revelar si el email existe.

    **Args:**
        db: Sesión activa de SQLAlchemy.
        data: Credenciales de login.

    **Returns:**
        Par de tokens access y refresh.

    **Raises:**
        SecurityError: Si las credenciales son incorrectas o el usuario está inactivo.
    """
    user = db.query(User).filter(User.email == data.email).first()

    if not user or not verify_password(data.password, user.hashed_password):
        raise SecurityError("Credenciales incorrectas.")

    if not user.is_active:
        raise SecurityError("Credenciales incorrectas.")

    access_token, refresh_token = create_token_pair(str(user.id), user.role)
    logger.info("user_logged_in", user_id=str(user.id))

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)

def refresh_tokens(refresh_token: str) -> TokenResponse:
    """
    Genera un nuevo par de tokens a partir de un refresh token válido.
    Rota el refresh token — el anterior queda revocado.

    **Args:**
        refresh_token: Refresh token vigente.

    **Returns:**
        Nuevo par de tokens access y refresh.

    **Raises:**
        SecurityError: Si el refresh token es inválido, expirado o revocado.
    """
    payload = decode_token(refresh_token, expected_type="refresh")

    revoke_token(refresh_token)

    access_token, new_refresh_token = create_token_pair(payload["sub"], payload["role"])
    logger.info("tokens_refreshed", user_id=payload["sub"])

    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)

def logout_user(access_token: str, refresh_token: str) -> None:
    """
    Revoca ambos tokens del usuario, invalidando la sesión completamente.

    **Args:**
        access_token: Access token activo a revocar.
        refresh_token: Refresh token activo a revocar.
    """
    revoke_token(access_token)
    revoke_token(refresh_token)
    logger.info("user_logged_out")