from pydantic import BaseModel, EmailStr, Field, field_validator
from src.core.security import sanitize_string

class RegisterRequest(BaseModel):
    """
    Schema de entrada para el registro de un nuevo usuario.
    """

    model_config = {"str_strip_whitespace": True, "frozen": True}

    email: EmailStr
    password: str = Field(min_length=8, max_length=64)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        """
        Valida que la contraseña cumpla requisitos mínimos de seguridad.

        **Args:**
            value: Contraseña en texto plano a validar.

        **Returns:**
            La misma contraseña si cumple los requisitos.

        **Raises:**
            ValueError: Si la contraseña no tiene la complejidad requerida.
        """
        has_upper  = any(c.isupper() for c in value)
        has_lower  = any(c.islower() for c in value)
        has_digit  = any(c.isdigit() for c in value)
        has_symbol = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in value)

        if not all([has_upper, has_lower, has_digit, has_symbol]):
            raise ValueError(
                "La contraseña debe contener al menos una mayúscula, "
                "una minúscula, un número y un símbolo."
            )
        return value

class LoginRequest(BaseModel):
    """
    Schema de entrada para el login.
    """

    model_config = {"str_strip_whitespace": True, "frozen": True}

    email: EmailStr
    password: str = Field(min_length=1, max_length=64)


class TokenResponse(BaseModel):
    """
    Schema de respuesta con los tokens de acceso y refresco.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """
    Schema de entrada para refrescar el access token.
    """

    refresh_token: str = Field(min_length=1)


class UserResponse(BaseModel):
    """
    Schema de respuesta con los datos públicos del usuario.
    """

    model_config = {"from_attributes": True}

    id: str
    email: str
    role: str
    is_active: bool