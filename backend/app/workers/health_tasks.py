"""Non-sensitive operational task for checking worker delivery."""

from app.infrastructure.messaging.celery_app import celery_app


@celery_app.task(name="talkfiesta.health.ping", ignore_result=True)
def ping() -> str:
    return "pong"
