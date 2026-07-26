from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "talkfiesta",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.writing_tasks",
        "app.workers.speaking_tasks",
        "app.workers.interview_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Fail fast when the broker is unreachable instead of blocking the API
    # request forever inside .delay(); callers handle the raised error.
    broker_connection_timeout=3,
    broker_transport_options={
        "max_retries": 2,
        "interval_start": 0,
        "interval_step": 0.2,
        "interval_max": 0.5,
    },
    task_publish_retry_policy={
        "max_retries": 2,
        "interval_start": 0,
        "interval_step": 0.2,
        "interval_max": 0.5,
    },
    result_backend_transport_options={
        "retry_policy": {
            "max_retries": 2,
            "interval_start": 0,
            "interval_step": 0.2,
            "interval_max": 0.5,
        },
    },
    redis_socket_connect_timeout=3,
    redis_socket_timeout=5,
)
