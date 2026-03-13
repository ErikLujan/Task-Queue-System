FROM python:3.12-slim

# Evita archivos .pyc y buffers en stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_FROZEN=1 \
    UV_NO_SYNC=0

WORKDIR /app

# Instala uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copia archivos de dependencias primero para aprovechar cache de Docker
COPY pyproject.toml uv.lock* ./

# Instala dependencias sin el proyecto en sí
RUN uv sync --frozen --no-install-project

# Copia el resto del código
COPY . .
RUN uv sync --frozen --no-dev

# Instala el proyecto completo
RUN adduser --disabled-password --gecos "" appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000