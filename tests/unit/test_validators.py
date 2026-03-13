import uuid
import pytest

from src.utils.validators import validate_uuid, validate_pagination
from src.core.exceptions import ValidationError

class TestValidateUUID:
    """
    Tests para la validación de UUIDs.
    """

    def test_uuid_valido_retorna_instancia(self):
        """
        Un UUID v4 válido debe retornar una instancia de uuid.UUID.
        """
        valid = str(uuid.uuid4())
        result = validate_uuid(valid)
        assert isinstance(result, uuid.UUID)

    def test_string_invalido_lanza_error(self):
        """
        Un string que no sea UUID debe lanzar ValidationError.
        """
        with pytest.raises(ValidationError):
            validate_uuid("no-soy-un-uuid")

    def test_uuid_v1_lanza_error(self):
        """
        Un UUID que no sea v4 debe lanzar ValidationError.
        """
        uuid_v1 = str(uuid.uuid1())
        with pytest.raises(ValidationError):
            validate_uuid(uuid_v1)

    def test_string_vacio_lanza_error(self):
        """
        Un string vacío debe lanzar ValidationError.
        """
        with pytest.raises(ValidationError):
            validate_uuid("")

class TestValidatePagination:
    """
    Tests para la validación de parámetros de paginación.
    """

    def test_valores_validos_retornan_tupla(self):
        """
        alores dentro del rango deben retornar la misma tupla.
        """
        assert validate_pagination(1, 10) == (1, 10)

    def test_page_cero_lanza_error(self):
        """
        Una página menor a 1 debe lanzar ValidationError.
        """
        with pytest.raises(ValidationError):
            validate_pagination(0, 10)

    def test_page_size_cero_lanza_error(self):
        """
        Un page_size de 0 debe lanzar ValidationError.
        """
        with pytest.raises(ValidationError):
            validate_pagination(1, 0)

    def test_page_size_supera_limite_lanza_error(self):
        """
        Un page_size mayor a 100 debe lanzar ValidationError.
        """
        with pytest.raises(ValidationError):
            validate_pagination(1, 101)

    def test_page_size_maximo_valido(self):
        """
        Un page_size de exactamente 100 debe ser válido.
        """
        assert validate_pagination(5, 100) == (5, 100)