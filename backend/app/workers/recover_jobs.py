"""Recover bounded batches of expired jobs and lost broker deliveries."""

import argparse
from datetime import timedelta

from sqlalchemy import func, or_, select

from app.core.config import settings
from app.infrastructure.database.sync_session import SyncSessionLocal
from app.modules.jobs.assessment_runner import recover_job
from app.modules.jobs.models import AiJob, OutboxEvent


def recover_batch(limit: int = 100) -> int:
    unpublished = (
        select(OutboxEvent.id)
        .where(OutboxEvent.ai_job_id == AiJob.id, OutboxEvent.published_at.is_(None))
        .exists()
    )
    last_publish = (
        select(func.max(OutboxEvent.published_at))
        .where(OutboxEvent.ai_job_id == AiJob.id)
        .correlate(AiJob)
        .scalar_subquery()
    )
    with SyncSessionLocal() as db:
        ids = list(
            db.scalars(
                select(AiJob.id)
                .where(
                    AiJob.job_type == "ASSESSMENT",
                    AiJob.status.in_(("RUNNING", "RETRYABLE", "PENDING")),
                    or_(
                        AiJob.next_attempt_at.is_(None),
                        AiJob.next_attempt_at <= func.now(),
                    ),
                    or_(
                        AiJob.lease_expires_at.is_(None),
                        AiJob.lease_expires_at <= func.now(),
                    ),
                    or_(
                        AiJob.status == "RUNNING",
                        (~unpublished)
                        & or_(
                            AiJob.status == "RETRYABLE",
                            func.coalesce(last_publish, AiJob.created_at)
                            <= func.now()
                            - timedelta(seconds=settings.celery_visibility_timeout),
                        ),
                    ),
                )
                .order_by(AiJob.created_at, AiJob.id)
                .limit(limit)
            )
        )
    # Recheck under locks because another recovery process may win the race.
    changed = 0
    for job_id in ids:
        changed += int(recover_job(job_id))
        if changed >= limit:
            break
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000:
        parser.error("limit must be between 1 and 1000")
    print(f"Recovered jobs: {recover_batch(args.limit)}")


if __name__ == "__main__":
    main()
