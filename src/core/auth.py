import bcrypt as _bcrypt
import redis

from datetime import datetime, timedelta, timezone
from typing import Literal
from jose import JWTError, jwt

from src.core.config import settings
from src.core.exceptions import SecurityError
from src.core.logging import get_logger

logger = get_logger(__name__)

# Expiración diferenciada — access token corto, refresh token largo
_ACCESS_TOKEN_EXPIRE_MINUTES = 15
_REFRESH_TOKEN_EXPIRE_DAYS   = 7
_ALGORITHM                   = "HS256"

# Cliente Redis para blacklist de tokens revocados
_redis_client = redis.from_url(str(settings.redis_url), decode_responses=True)

def hash_password(password: str) -> str:
    """
    Genera el hash bcrypt de una contraseña en texto plano.
    Trunca a 72 bytes antes de hashear — límite nativo de bcrypt.

    **Args:**
        password: Contraseña en texto plano.

    **Returns:**
        Hash bcrypt listo para almacenar en la DB.
    """
    password_bytes = password.encode("utf-8")[:72]
    salt = _bcrypt.gensalt(rounds=12)
    return _bcrypt.hashpw(password_bytes, salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Compara una contraseña en texto plano contra su hash almacenado.
    Usa comparación en tiempo constante para prevenir timing attacks.

    **Args:**
        plain_password: Contraseña ingresada por el usuario.
        hashed_password: Hash almacenado en la DB.

    **Returns:**
        True si la contraseña es correcta, False en caso contrario.
    """
    password_bytes = plain_password.encode("utf-8")[:72]
    return _bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))

def _create_token(
    subject: str,
    role: str,
    token_type: Literal["access", "refresh"],
) -> str:
    """
    Genera un JWT firmado con el tipo, subject y expiración indicados.

    **Args:**
        subject: Identificador del usuario (su UUID como string).
        role: Rol del usuario a incluir en el payload.
        token_type: Tipo de token — access o refresh.

    **Returns:**
        JWT firmado como string.
    """
    if token_type == "access":
        expire = datetime.now(timezone.utc) + timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES)
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=_REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub":  subject,
        "role": role,
        "type": token_type,
        "exp":  expire,
        "iat":  datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)

def create_token_pair(user_id: str, role: str) -> tuple[str, str]:
    """
    Genera un par de tokens — access y refresh — para un usuario autenticado.

    **Args:**
        user_id: UUID del usuario como string.
        role: Rol del usuario.

    **Returns:**
        Tupla (access_token, refresh_token).
    """
    access_token  = _create_token(user_id, role, "access")
    refresh_token = _create_token(user_id, role, "refresh")
    return access_token, refresh_token

def decode_token(token: str, expected_type: Literal["access", "refresh"]) -> dict:
    """
    Valida y decodifica un JWT, verificando firma, expiración y blacklist.

    **Args:**
        token: JWT a validar.
        expected_type: Tipo esperado del token (access o refresh).

    **Returns:**
        Payload decodificado si el token es válido.

    **Raises:**
        SecurityError: Si el token es inválido, expirado, revocado o del tipo incorrecto.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
    except JWTError as exc:
        raise SecurityError("Token inválido o expirado.") from exc

    if payload.get("type") != expected_type:
        raise SecurityError(f"Se esperaba un token de tipo '{expected_type}'.")

    if _is_token_blacklisted(token):
        raise SecurityError("Token revocado.")

    return payload

def revoke_token(token: str) -> None:
    """
    Agrega un token a la blacklist en Redis con TTL igual a su tiempo restante.
    Garantiza que el token no pueda usarse después del logout.

    **Args:**
        token: JWT a revocar.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[_ALGORITHM],
            options={"verify_exp": False},
        )
        exp = payload.get("exp", 0)
        ttl = max(0, exp - int(datetime.now(timezone.utc).timestamp()))
        if ttl > 0:
            _redis_client.setex(f"blacklist:{token}", ttl, "1")
            logger.info("token_revoked", user_id=payload.get("sub"))
    except JWTError:
        pass

def _is_token_blacklisted(token: str) -> bool:
    """
    Verifica si un token está en la blacklist de Redis.

    **Args:**
        token: JWT a verificar.

    **Returns:**
        True si el token fue revocado, False en caso contrario.
    """
    return _redis_client.exists(f"blacklist:{token}") == 1