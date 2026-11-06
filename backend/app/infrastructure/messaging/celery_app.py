"""Celery transport configuration; PostgreSQL remains the job/result authority."""

from celery import Celery
from kombu import Exchange, Queue

from app.core.config import settings

OPERATIONS_QUEUE = "talkfiesta.operations"
ASSESSMENT_QUEUE = "talkfiesta.assessments"
SPEAKING_QUEUE = "talkfiesta.speaking"
VOCABULARY_QUEUE = "talkfiesta.vocabulary"
WRITING_QUEUE = "talkfiesta.writing"
TASK_EXCHANGE = Exchange("talkfiesta", type="direct", durable=True)

celery_app = Celery(
    "talkfiesta",
    broker=settings.celery_broker_url,
    include=[
        "app.workers.health_tasks",
        "app.workers.assessment_tasks",
        "app.workers.speaking_tasks",
        "app.workers.vocabulary_tasks",
        "app.workers.writing_tasks",
    ],
)
celery_app.conf.update(
    task_queues=(
        Queue(SPEAKING_QUEUE, TASK_EXCHANGE, routing_key=SPEAKING_QUEUE, durable=True),
        Queue(
            VOCABULARY_QUEUE,
            TASK_EXCHANGE,
            routing_key=VOCABULARY_QUEUE,
            durable=True,
        ),
        Queue(
            WRITING_QUEUE,
            TASK_EXCHANGE,
            routing_key=WRITING_QUEUE,
            durable=True,
        ),
        Queue(
            OPERATIONS_QUEUE, TASK_EXCHANGE, routing_key=OPERATIONS_QUEUE, durable=True
        ),
        Queue(
            ASSESSMENT_QUEUE, TASK_EXCHANGE, routing_key=ASSESSMENT_QUEUE, durable=True
        ),
    ),
    task_default_queue=OPERATIONS_QUEUE,
    task_default_exchange="talkfiesta",
    task_default_exchange_type="direct",
    task_default_routing_key=OPERATIONS_QUEUE,
    task_create_missing_queues=False,
    task_routes={"talkfiesta.health.ping": {"queue": OPERATIONS_QUEUE}},
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_accept_content=["json"],
    # No Redis result backend: domain status/results live in ai_jobs and assessments.
    result_backend=None,
    task_ignore_result=True,
    task_store_errors_even_if_ignored=False,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_concurrency=settings.celery_worker_concurrency,
    worker_max_tasks_per_child=100,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    task_time_limit=settings.celery_task_time_limit,
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=None,
    broker_connection_timeout=5,
    broker_transport_options={
        "visibility_timeout": settings.celery_visibility_timeout,
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
        "global_keyprefix": "talkfiesta:",
    },
    task_publish_retry=True,
    task_publish_retry_policy={
        "max_retries": 3,
        "interval_start": 0,
        "interval_step": 1,
        "interval_max": 3,
    },
    enable_utc=True,
    timezone="UTC",
    worker_hijack_root_logger=False,
    worker_send_task_events=False,
    task_send_sent_event=False,
    # Added when the durable dispatcher exists; do not schedule empty scaffolds.
    beat_schedule={},
)
