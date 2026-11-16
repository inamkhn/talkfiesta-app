"""Celery worker entry point for Content Factory child generation jobs."""

from __future__ import annotations

import logging
from uuid import UUID

from billiard.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select

from app.core.config import settings
from app.infrastructure.ai.tracing import build_assessment_trace_config
from app.infrastructure.database.sync_session import SyncSessionLocal
from app.infrastructure.messaging.celery_app import celery_app
from app.modules.content.ai.budgeted_model import model_for_claim
from app.modules.content.ai.persistence import persist_vocabulary_unit
from app.modules.content.ai.vocab_graph import build_vocab_generation_graph
from app.modules.content.blueprint_loader import get_day_blueprint
from app.modules.content.budget import ContentBudgetExceeded
from app.modules.content.models import ContentItem
from app.modules.jobs import content_runner as runner
from app.modules.jobs.assessment_runner import LostClaimError, RetryableEvaluationError
from app.modules.jobs.models import AiJob

logger = logging.getLogger(__name__)


def execute_content_generation(job_id: str) -> str:
    """Execute one fenced `CONTENT_AUTHORING` child job."""
    if not settings.content_generation_enabled:
        return "disabled"

    claim = runner.claim_job(UUID(job_id))
    if claim is None:
        return "skipped"

    try:
        with SyncSessionLocal() as db:
            job = db.get(AiJob, claim.job_id)
            ctx = dict(job.job_context or {}) if job is not None else {}

        resolved = get_day_blueprint(
            ctx["cefr_level"],
            int(ctx["cycle"]),
            int(ctx["day"]),
            goal_variant=ctx.get("goal_variant", "GENERAL"),
            blueprint_version=ctx.get("blueprint_version"),
        )

        if ctx.get("dry_run"):
            runner.finish_job(
                claim,
                result_summary={
                    "dry_run": True,
                    "module": ctx["module"],
                    "day": resolved.day,
                    "theme": resolved.day_blueprint.theme,
                    "blueprint_version": resolved.blueprint_version,
                },
            )
            return "dry_run_succeeded"

        if ctx.get("module") == "VOCABULARY":
            with SyncSessionLocal() as db:
                prior_titles = list(
                    db.scalars(
                        select(ContentItem.title).where(
                            ContentItem.release_key == ctx["release_key"],
                            ContentItem.kind == "VOCAB_WORD",
                        )
                    )
                )

            run_id, trace_config = build_assessment_trace_config(
                job_id=claim.job_id,
                attempt_id=claim.job_id,
            )
            final_state = build_vocab_generation_graph().invoke(
                {
                    "job_id": str(claim.job_id),
                    "generation_batch_key": ctx.get("generation_batch_key", ""),
                    "release_key": str(ctx["release_key"]),
                    "prompt_bundle_version": str(
                        ctx.get("prompt_bundle_version", "content-factory-v1")
                    ),
                    "context": resolved,
                    "prior_words": prior_titles,
                    "retry_count": 0,
                    "max_retries": 2,
                    "report_stage": lambda stage: runner.report_stage(claim, stage),
                    "invoke_model": model_for_claim(claim),
                },
                config=trace_config,
            )
            if final_state.get("outcome") == "FAILED" or not final_state.get("unit"):
                runner.fail_job(claim, retryable=False, code="VALIDATION_EXHAUSTED")
                return "failed_validation"

            runner.report_stage(claim, "SAVING_CONTENT")
            with SyncSessionLocal.begin() as db:
                persist_vocabulary_unit(
                    db,
                    claim=claim,
                    unit=final_state["unit"],
                    review_report=final_state["review_report"],
                    outcome=final_state["outcome"],
                    validation_warnings=final_state.get("validation_warnings", []),
                    langsmith_run_id=str(run_id),
                )
            return "succeeded"

        raise NotImplementedError(
            f"Live LLM generation for module={ctx.get('module')} will be wired in Phase 4."
        )
    except LostClaimError:
        logger.warning("content_generation_claim_lost job_id=%s", job_id)
        return "lost_claim"
    except Exception as exc:  # noqa: BLE001
        retryable = isinstance(exc, (RetryableEvaluationError, SoftTimeLimitExceeded))
        try:
            runner.fail_job(
                claim,
                retryable=retryable,
                code=(
                    "GENERATION_BUDGET_EXHAUSTED"
                    if isinstance(exc, ContentBudgetExceeded)
                    else "GENERATION_TRANSIENT"
                    if retryable
                    else "GENERATION_FAILED"
                ),
            )
        except LostClaimError:
            logger.warning("content_generation_claim_lost job_id=%s", job_id)
        logger.warning(
            "content_generation_failed job_id=%s error_type=%s",
            job_id,
            type(exc).__name__,
        )
        return "failed"


if settings.content_generation_enabled:
    celery_app.task(name="talkfiesta.content.generate_unit", ignore_result=True)(
        execute_content_generation
    )
