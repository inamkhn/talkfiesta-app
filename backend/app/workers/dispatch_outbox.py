"""Standalone PostgreSQL-to-Celery dispatcher; run separately from Redis workers."""

import argparse
import logging
import signal
from threading import Event

from app.core.config import settings
from app.infrastructure.database import model_registry  # noqa: F401
from app.infrastructure.messaging.celery_app import (
    ASSESSMENT_QUEUE,
    SPEAKING_QUEUE,
    celery_app,
)
from app.modules.jobs.outbox import claim_next, mark_published, record_failure

logger = logging.getLogger(__name__)
ASSESSMENT_TASK = "talkfiesta.assessment.execute"
SPEAKING_TASK = "talkfiesta.speaking.execute"


def require_handler() -> None:
    if not settings.outbox_dispatch_enabled:
        raise RuntimeError(
            "Outbox publishing is disabled. Enable only after the configured workers are deployed."
        )
    celery_app.loader.import_default_modules()
    enabled = []
    if settings.assessment_execution_enabled:
        enabled.append(ASSESSMENT_TASK)
    if settings.speaking_execution_enabled:
        enabled.append(SPEAKING_TASK)
    if not enabled or any(task not in celery_app.tasks for task in enabled):
        raise RuntimeError(
            "Every enabled evaluation handler must be registered before dispatch."
        )


def dispatch_batch(stop: Event | None = None) -> int:
    require_handler()
    published = 0
    for _ in range(settings.outbox_batch_size):
        if stop is not None and stop.is_set():
            break
        claim = claim_next()
        if claim is None:
            break
        try:
            # One publish attempt per DB claim; durable backoff lives in PostgreSQL.
            # Deterministic task ID aids correlation, not Celery deduplication.
            task, queue = (
                (SPEAKING_TASK, SPEAKING_QUEUE)
                if claim.job_type == "SPEAKING_FEEDBACK"
                else (ASSESSMENT_TASK, ASSESSMENT_QUEUE)
            )
            celery_app.send_task(
                task,
                args=[str(claim.job_id)],
                task_id=str(claim.event_id),
                queue=queue,
                routing_key=queue,
                serializer="json",
                retry=False,
                ignore_result=True,
            )
        except Exception as exc:  # noqa: BLE001 - persist failure without leaking broker credentials
            record_failure(claim)
            logger.warning(
                "outbox_publish_failed event_id=%s error_type=%s",
                claim.event_id,
                type(exc).__name__,
            )
            continue
        if mark_published(claim):
            published += 1
            logger.info(
                "outbox_published event_id=%s job_id=%s", claim.event_id, claim.job_id
            )
        else:
            logger.warning("outbox_claim_superseded event_id=%s", claim.event_id)
    return published


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once", action="store_true", help="Dispatch one bounded batch and exit."
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    require_handler()
    stop = Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stop.set())
    while not stop.is_set():
        try:
            count = dispatch_batch(stop)
            logger.info("outbox_batch_complete published=%s", count)
        except Exception as exc:  # noqa: BLE001 - keep polling after a database outage
            logger.error("outbox_batch_failed error_type=%s", type(exc).__name__)
            if args.once:
                raise SystemExit(1) from None
        if args.once:
            return
        stop.wait(settings.outbox_poll_seconds)


if __name__ == "__main__":
    main()
