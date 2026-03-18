from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry

REGISTRY = CollectorRegistry(auto_describe=True)

# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

JOBS_TOTAL = Counter(
    name="jobs_total",
    documentation="Cantidad total de jobs encolados por tipo.",
    labelnames=["job_type"],
    registry=REGISTRY,
)

JOBS_BY_STATUS = Gauge(
    name="jobs_by_status",
    documentation="Cantidad actual de jobs por estado.",
    labelnames=["status"],
    registry=REGISTRY,
)

JOB_PROCESSING_SECONDS = Histogram(
    name="job_processing_seconds",
    documentation="Tiempo de procesamiento de jobs en segundos por tipo.",
    labelnames=["job_type", "status"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
    registry=REGISTRY,
)

JOB_ERRORS_TOTAL = Counter(
    name="job_errors_total",
    documentation="Cantidad total de jobs fallidos por tipo.",
    labelnames=["job_type"],
    registry=REGISTRY,
)

JOB_RETRIES_TOTAL = Counter(
    name="job_retries_total",
    documentation="Cantidad total de reintentos por tipo de job.",
    labelnames=["job_type"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

HTTP_REQUESTS_TOTAL = Counter(
    name="http_requests_total",
    documentation="Cantidad total de requests HTTP por endpoint y status code.",
    labelnames=["method", "endpoint", "status_code"],
    registry=REGISTRY,
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    name="http_request_duration_seconds",
    documentation="Duración de requests HTTP en segundos por endpoint.",
    labelnames=["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    registry=REGISTRY,
)