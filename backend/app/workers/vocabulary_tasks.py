"""Vocabulary contextual sentence task entry point; PostgreSQL owns claims, retries, and results."""

import logging
from uuid import UUID

from billiard.exceptions import SoftTimeLimitExceeded

from app.core.config import settings
from app.infrastructure.messaging.celery_app import celery_app
from app.modules.jobs import vocabulary_runner as runner
from app.modules.jobs.assessment_runner import LostClaimError, RetryableEvaluationError

logger = logging.getLogger(__name__)


def execute_vocabulary(job_id: str) -> None:
    claim = runner.claim_job(UUID(job_id))
    if claim is None:
        return
    try:
        from app.modules.vocabulary.ai import evaluate

        evidence, fingerprint = runner.load_evidence(claim)
        context_results, trace_id = evaluate(claim, evidence)
        runner.report_stage(claim, "SAVING_RESULTS")
        runner.finish(claim, fingerprint, context_results, trace_id)
    except LostClaimError:
        logger.warning("vocabulary_claim_lost job_id=%s", job_id)
    except Exception as exc:  # noqa: BLE001 - persist only sanitized operational codes
        retryable = isinstance(exc, (RetryableEvaluationError, SoftTimeLimitExceeded))
        try:
            runner.fail(
                claim,
                retryable,
                "EVALUATION_TRANSIENT" if retryable else "EVALUATION_FAILED",
            )
        except LostClaimError:
            logger.warning("vocabulary_claim_lost job_id=%s", job_id)
        logger.warning(
            "vocabulary_failed job_id=%s error_type=%s", job_id, type(exc).__name__
        )


if settings.vocabulary_execution_enabled:
    celery_app.task(name="talkfiesta.vocabulary.execute", ignore_result=True)(
        execute_vocabulary
    )

