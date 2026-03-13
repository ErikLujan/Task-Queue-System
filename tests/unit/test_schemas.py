import pytest
from pydantic import ValidationError as PydanticValidationError
from src.schemas.task_payload import EmailTaskPayload, ImageTaskPayload, ReportTaskPayload
from src.core.exceptions import SecurityError

class TestEmailTaskPayload:
    """
    Tests para el schema de payload de tareas de email.
    """

    def test_payload_valido(self):
        """
        Un payload bien formado debe instanciarse sin errores.
        """
        payload = EmailTaskPayload(
            recipient="test@example.com",
            subject="Asunto de prueba",
            body="Cuerpo del mensaje.",
        )
        assert payload.recipient == "test@example.com"

    def test_email_invalido_lanza_error(self):
        """
        Un email con formato incorrecto debe lanzar error de validación.
        """
        with pytest.raises(PydanticValidationError):
            EmailTaskPayload(
                recipient="no-es-un-email",
                subject="Asunto",
                body="Cuerpo",
            )

    def test_subject_vacio_lanza_error(self):
        """
        Un subject vacío debe lanzar error de validación.
        """
        with pytest.raises(PydanticValidationError):
            EmailTaskPayload(recipient="a@b.com", subject="", body="Cuerpo")

    def test_inyeccion_en_subject_lanza_error(self):
        """
        Un intento de inyección en el subject debe lanzar SecurityError.
        """
        with pytest.raises(SecurityError):
            EmailTaskPayload(
                recipient="a@b.com",
                subject="' UNION SELECT * FROM users",
                body="Cuerpo",
            )

class TestImageTaskPayload:
    """
    Tests para el schema de payload de tareas de procesamiento de imágenes.
    """

    def test_payload_valido(self):
        """
        Un payload bien formado debe instanciarse sin errores.
        """
        payload = ImageTaskPayload(
            filename="foto.jpg",
            operations=["grayscale", "resize"],
            output_format="jpeg",
        )
        assert "grayscale" in payload.operations

    def test_operacion_no_permitida_lanza_error(self):
        """
        Una operación fuera de la whitelist debe lanzar error de validación.
        """
        with pytest.raises(PydanticValidationError, match="no permitidas"):
            ImageTaskPayload(
                filename="foto.jpg",
                operations=["eliminar_todo"],
            )

    def test_formato_invalido_lanza_error(self):
        """
        Un formato de salida no soportado debe lanzar error de validación.
        """
        with pytest.raises(PydanticValidationError):
            ImageTaskPayload(filename="foto.jpg", operations=["flip"], output_format="bmp")

    def test_lista_operaciones_vacia_lanza_error(self):
        """
        Una lista de operaciones vacía debe lanzar error de validación.
        """
        with pytest.raises(PydanticValidationError):
            ImageTaskPayload(filename="foto.jpg", operations=[])

class TestReportTaskPayload:
    """
    Tests para el schema de payload de tareas de generación de reportes.
    """

    def test_payload_valido(self):
        """
        Un payload bien formado debe instanciarse sin errores.
        """
        payload = ReportTaskPayload(
            report_type="csv",
            dataset_id="ventas_2024",
        )
        assert payload.report_type == "csv"

    def test_tipo_invalido_lanza_error(self):
        """
        Un tipo de reporte no soportado debe lanzar error de validación.
        """
        with pytest.raises(PydanticValidationError):
            ReportTaskPayload(report_type="xml", dataset_id="ventas")

    def test_filtro_con_clave_invalida_lanza_error(self):
        """
        Una clave de filtro con caracteres especiales debe lanzar error.
        """
        with pytest.raises(PydanticValidationError, match="inválida"):
            ReportTaskPayload(
                report_type="csv",
                dataset_id="ventas",
                filters={"clave con espacios": "valor"},
            )

    def test_filtro_con_valor_muy_largo_lanza_error(self):
        """
        Un valor de filtro que supere 200 caracteres debe lanzar error.
        """
        with pytest.raises(PydanticValidationError):
            ReportTaskPayload(
                report_type="pdf",
                dataset_id="ventas",
                filters={"campo": "x" * 201},
            )