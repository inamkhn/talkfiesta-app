"""Assessment task registration is gated until the real evaluator is available."""

import logging
from uuid import UUID

from billiard.exceptions import SoftTimeLimitExceeded

from app.core.config import settings
from app.infrastructure.messaging.celery_app import celery_app
from app.modules.jobs.assessment_runner import (
    LostClaimError,
    RetryableEvaluationError,
    claim_job,
    fail,
    finish,
    report_stage,
)

logger = logging.getLogger(__name__)


def execute_assessment(job_id: str) -> None:
    claim = claim_job(UUID(job_id))
    if claim is None:
        return
    try:
        from app.modules.assessment.ai.evaluators import evaluate_assessment
        from app.modules.assessment.ai.evidence import load_assessment_evidence

        evidence = load_assessment_evidence(claim.job_id, claim.token)
        result = evaluate_assessment(
            evidence, lambda stage: report_stage(claim, stage), claim=claim
        )
        report_stage(claim, "SAVING_RESULTS")
        finish(claim, result)
    except LostClaimError:
        logger.warning("assessment_claim_lost job_id=%s", job_id)
    except Exception as exc:  # noqa: BLE001 - persist sanitized failure, never provider/learner text
        retryable = isinstance(exc, (RetryableEvaluationError, SoftTimeLimitExceeded))
        try:
            fail(
                claim,
                retryable=retryable,
                code="EVALUATION_TRANSIENT" if retryable else "EVALUATION_FAILED",
            )
        except LostClaimError:
            logger.warning("assessment_claim_lost job_id=%s", job_id)
        logger.warning(
            "assessment_failed job_id=%s error_type=%s", job_id, type(exc).__name__
        )


if settings.assessment_execution_enabled:
    from app.modules.assessment.ai import evaluators

    if not callable(getattr(evaluators, "evaluate_assessment", None)):
        raise RuntimeError(
            "Assessment execution requires the real evaluate_assessment implementation."
        )
    celery_app.task(name="talkfiesta.assessment.execute", ignore_result=True)(
        execute_assessment
    )
