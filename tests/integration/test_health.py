import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.monitoring.health import check_redis, check_database, full_health_report


class TestCheckRedis:
    """
    Tests de integración para el health check de Redis.
    """

    def test_redis_disponible_retorna_ok(self) -> None:
        """
        Cuando Redis responde al ping debe retornar status ok.
        """
        with patch("src.monitoring.health.redis.from_url") as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client
            result = check_redis()
        assert result["status"] == "ok"

    def test_redis_no_disponible_retorna_error(self) -> None:
        """
        Cuando Redis no responde debe retornar status error con detalle.
        """
        with patch("src.monitoring.health.redis.from_url") as mock_redis:
            mock_redis.return_value.ping.side_effect = ConnectionError("sin conexión")
            result = check_redis()
        assert result["status"] == "error"
        assert "detail" in result


class TestCheckDatabase:
    """
    Tests de integración para el health check de la base de datos.
    """

    @pytest.mark.asyncio
    async def test_db_disponible_retorna_ok(self) -> None:
        """
        Cuando la DB responde correctamente debe retornar status ok.
        """
        mock_db = AsyncMock()
        result = await check_database(mock_db)
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_db_no_disponible_retorna_error(self) -> None:
        """
        Cuando la DB falla debe retornar status error con detalle.
        """
        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("conexión rechazada")
        result = await check_database(mock_db)
        assert result["status"] == "error"
        assert "detail" in result


class TestFullHealthReport:
    """
    Tests para el reporte completo de salud del sistema.
    """

    @pytest.mark.asyncio
    async def test_todos_ok_retorna_status_ok(self) -> None:
        """
        Cuando todos los servicios están bien el status general debe ser ok.
        """
        mock_db = AsyncMock()
        with patch("src.monitoring.health.redis.from_url"):
            report = await full_health_report(mock_db)
        assert report["status"] == "ok"
        assert "services" in report

    @pytest.mark.asyncio
    async def test_un_servicio_caido_retorna_degraded(self) -> None:
        """
        Si algún servicio falla el status general debe ser degraded.
        """
        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("DB caída")
        with patch("src.monitoring.health.redis.from_url"):
            report = await full_health_report(mock_db)
        assert report["status"] == "degraded"
