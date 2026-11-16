"""Transactional persistence for Content Factory units (words + lesson + job completion)."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.content.contracts import AiReviewReport, VocabularyUnitOutput
from app.modules.content.models import ContentItem
from app.modules.jobs.assessment_runner import JobClaim
from app.modules.jobs.content_runner import require_claim
from app.modules.jobs.models import AiJob


def resolve_vocab_lesson_body(
    unit: VocabularyUnitOutput,
    key_to_id: dict[str, UUID],
) -> dict:
    """Resolve temporary `word_item_keys` in the lesson and exercises to saved `ContentItem.id` UUIDs."""
    lesson_body = unit.lesson.model_dump(mode="json")
    lesson_body["word_content_ids"] = [
        str(key_to_id[key]) for key in unit.lesson.word_item_keys
    ]
    for ex in lesson_body.get("exercises", []):
        if ex.get("type") == "USE_IN_CONTEXT" and ex.get("word_item_key"):
            ref_key = ex["word_item_key"]
            if ref_key in key_to_id:
                ex["word_id"] = str(key_to_id[ref_key])
    return lesson_body


def persist_vocabulary_unit(
    db: Session,
    *,
    claim: JobClaim,
    unit: VocabularyUnitOutput,
    review_report: AiReviewReport,
    outcome: str,
    validation_warnings: list[str],
    langsmith_run_id: str | None = None,
) -> dict:
    """Persist 10 `VOCAB_WORD` rows, 1 `VOCABULARY_LESSON` row, and complete the child `AiJob` atomically."""
    job, now = require_claim(db, claim)
    ctx = dict(job.job_context or {})
    cefr_level = str(ctx["cefr_level"])
    cycle = int(ctx["cycle"])
    day = int(ctx["day"])
    goal_variant = str(ctx.get("goal_variant", "GENERAL"))
    release_key = str(ctx["release_key"])
    batch_key = job.generation_batch_key

    target_status = "REVIEW" if outcome == "PASS_TO_REVIEW" else "DRAFT"
    review_note = (
        None
        if outcome == "PASS_TO_REVIEW"
        else f"AI review flagged for editor attention: {review_report.recommended_action}"
    )

    gen_keys = [f"{release_key}:{w.item_key}" for w in unit.words]
    lesson_gen_key = f"{release_key}:{unit.lesson.item_key}"
    existing_by_key = {
        row.generation_item_key: row
        for row in db.scalars(
            select(ContentItem).where(
                ContentItem.generation_item_key.in_([*gen_keys, lesson_gen_key])
            )
        )
        if row.generation_item_key is not None
    }

    key_to_id: dict[str, UUID] = {}
    word_ids: list[str] = []
    for word in unit.words:
        gen_key = f"{release_key}:{word.item_key}"
        existing = existing_by_key.get(gen_key)
        if existing is not None:
            key_to_id[word.item_key] = existing.id
            word_ids.append(str(existing.id))
            continue
        word_id = uuid4()
        key_to_id[word.item_key] = word_id
        word_ids.append(str(word_id))
        db.add(
            ContentItem(
                id=word_id,
                kind="VOCAB_WORD",
                module="VOCABULARY",
                release_key=release_key,
                cefr_level=cefr_level,
                title=word.word,
                body=word.model_dump(mode="json"),
                status=target_status,
                origin="AI",
                generation_batch_key=batch_key,
                generation_item_key=gen_key,
                content_version=1,
                review_notes=review_note,
            )
        )

    lesson_body = resolve_vocab_lesson_body(unit, key_to_id)
    existing_lesson = existing_by_key.get(lesson_gen_key)
    if existing_lesson is not None:
        lesson_id = existing_lesson.id
    else:
        lesson_id = uuid4()
        db.add(
            ContentItem(
                id=lesson_id,
                kind="VOCABULARY_LESSON",
                module="VOCABULARY",
                release_key=release_key,
                cycle=cycle,
                day=day,
                cefr_level=cefr_level,
                goal_variant=goal_variant,
                slot="CORE",
                title=f"Day {day}: {unit.lesson.theme}",
                body=lesson_body,
                status=target_status,
                origin="AI",
                generation_batch_key=batch_key,
                generation_item_key=lesson_gen_key,
                content_version=1,
                review_notes=review_note,
            )
        )

    summary = {
        "module": "VOCABULARY",
        "day": day,
        "release_key": release_key,
        "lesson_id": str(lesson_id),
        "word_ids": word_ids,
        "item_status": target_status,
        "review_decision": review_report.overall_decision,
        "review_scores": review_report.scores.model_dump(mode="json"),
        "warnings": [*validation_warnings, *review_report.warnings],
    }
    job.status = "SUCCEEDED"
    job.stage = "DONE"
    job.finished_at = now
    job.claim_token = None
    job.lease_expires_at = None
    job.model = settings.openai_evaluation_model
    job.result_summary = summary
    if langsmith_run_id is not None:
        job.langsmith_run_id = str(langsmith_run_id)[:80]
    return summary

