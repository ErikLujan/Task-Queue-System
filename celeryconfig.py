from src.core.config import settings

# Archivo de configuración externo de Celery.
# Permite sobrescribir settings sin tocar el código de la app.

broker_url = str(settings.redis_url)
result_backend = str(settings.redis_url)

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]

task_acks_late = True
task_reject_on_worker_lost = True
worker_prefetch_multiplier = 1  # --> Un mensaje a la vez por worker — más justo bajo carga

result_expires = 3600  # --> Los resultados en Redis expiran en 1 hora