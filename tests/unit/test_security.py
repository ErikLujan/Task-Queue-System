import pytest

from src.core.security import sanitize_string, secure_filename, validate_file
from src.core.exceptions import SecurityError, ValidationError
from pathlib import Path

class TestSanitizeString:
    """
    Tests para la función de sanitización de strings.
    """

    def test_string_limpio_pasa_sin_cambios(self):
        """
        Un string normal no debe ser modificado ni rechazado.
        """
        result = sanitize_string("nombre_de_archivo_valido")
        assert result == "nombre_de_archivo_valido"

    def test_detecta_sql_injection_union(self):
        """
        Debe rechazar strings con palabras clave de SQL injection.
        """
        with pytest.raises(SecurityError):
            sanitize_string("' UNION SELECT * FROM users--", field_name="input")

    def test_detecta_sql_injection_drop(self):
        """
        Debe rechazar intentos de DROP TABLE.
        """
        with pytest.raises(SecurityError):
            sanitize_string("DROP TABLE jobs", field_name="input")

    def test_detecta_path_traversal(self):
        """
        Debe rechazar strings con secuencias de path traversal.
        """
        with pytest.raises(SecurityError):
            sanitize_string("../../etc/passwd", field_name="path")

    def test_detecta_null_byte(self):
        """
        Debe rechazar strings que contengan null bytes.
        """
        with pytest.raises(SecurityError):
            sanitize_string("archivo\x00.exe", field_name="filename")

    def test_field_name_aparece_en_mensaje(self):
        """
        El mensaje de error debe incluir el nombre del campo afectado.
        """
        with pytest.raises(SecurityError, match="campo_test"):
            sanitize_string("' OR '1'='1", field_name="campo_test")

class TestSecureFilename:
    """
    Tests para la generación de nombres de archivo seguros.
    """

    def test_genera_nombre_con_hash(self):
        """
        El nombre generado debe contener un hash único de 8 caracteres.
        """
        result = secure_filename("imagen.jpg")
        parts = result.rsplit(".", 1)
        assert len(parts) == 2
        stem_parts = parts[0].rsplit("_", 1)
        assert len(stem_parts[-1]) == 8

    def test_elimina_caracteres_especiales(self):
        """
        Debe eliminar caracteres especiales del nombre original.
        """
        result = secure_filename("mi archivo (1).jpg")
        assert " " not in result
        assert "(" not in result
        assert ")" not in result

    def test_nombre_vacio_lanza_error(self):
        """
        Un nombre que quede vacío tras sanitizar debe lanzar ValidationError.
        """
        with pytest.raises(ValidationError):
            secure_filename(".....")

    def test_extension_en_minusculas(self):
        """
        La extensión del archivo debe quedar en minúsculas.
        """
        result = secure_filename("IMAGEN.JPG")
        assert result.endswith(".jpg")

    def test_dos_llamadas_generan_nombres_distintos(self):
        """
        Dos llamadas con el mismo nombre deben generar resultados únicos.
        """
        result1 = secure_filename("foto.png")
        result2 = secure_filename("foto.png")
        assert result1 != result2