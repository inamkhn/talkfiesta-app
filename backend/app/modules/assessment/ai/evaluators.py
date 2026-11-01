"""Entry point for worker-executed initial assessment evaluation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.infrastructure.ai.tracing import build_assessment_trace_config
from app.infrastructure.database.sync_session import SyncSessionLocal
from app.modules.assessment.ai.graph import build_assessment_graph
from app.modules.assessment.ai.state import (
    FrozenAssessment,
    FrozenSpeakingEvidence,
    FrozenWritingEvidence,
)
from app.modules.assessment.models import AssessmentAttempt, AssessmentResponse
from app.modules.assessment.placement_policy import ObjectiveItemOutcome
from app.modules.assessment.schemas import PublicPlacement
from app.modules.assessment.selection import SEQUENCE, valid_question
from app.modules.content.models import ContentItem
from app.modules.jobs.models import AiJob
from app.modules.media.models import MediaUpload


def load_frozen_assessment(job_id: UUID) -> FrozenAssessment:
    """Load frozen assessment answers, rubrics, and audio refs without holding a transaction."""
    with SyncSessionLocal() as db:
        job = db.scalar(
            select(AiJob).where(AiJob.id == job_id, AiJob.job_type == "ASSESSMENT")
        )
        if job is None or job.assessment_attempt_id is None or job.user_id is None:
            raise ValueError("Assessment job not found or missing attempt reference.")

        attempt = db.scalar(
            select(AssessmentAttempt).where(
                AssessmentAttempt.id == job.assessment_attempt_id,
                AssessmentAttempt.user_id == job.user_id,
            )
        )
        if attempt is None:
            raise ValueError("Assessment attempt not found.")

        rows = list(
            db.scalars(
                select(AssessmentResponse)
                .where(AssessmentResponse.assessment_attempt_id == attempt.id)
                .order_by(AssessmentResponse.position)
            )
        )
        if len(rows) != len(SEQUENCE) or [r.position for r in rows] != list(
            range(1, len(SEQUENCE) + 1)
        ):
            raise ValueError("Submitted assessment responses are incomplete.")

        items = {
            item.id: item
            for item in db.scalars(
                select(ContentItem).where(
                    ContentItem.kind == "ASSESSMENT_QUESTION",
                    ContentItem.status == "PUBLISHED",
                    ContentItem.release_key == attempt.content_release,
                )
            )
            if valid_question(item)
        }

        grammar_outcomes: list[ObjectiveItemOutcome] = []
        vocabulary_outcomes: list[ObjectiveItemOutcome] = []
        writing_evidence: FrozenWritingEvidence | None = None
        speaking_evidence: FrozenSpeakingEvidence | None = None

        for row, expected_skill in zip(rows, SEQUENCE, strict=True):
            item = items.get(row.question_content_id)
            if item is None or item.body.get("skill") != expected_skill:
                raise ValueError("Assigned question content is missing or mismatched.")
            answer = row.answer if isinstance(row.answer, dict) else {}

            if expected_skill in ("GRAMMAR", "VOCABULARY"):
                correct = (
                    row.grading.get("correct")
                    if isinstance(row.grading, dict)
                    else None
                )
                if type(correct) is not bool or item.cefr_level is None:
                    raise ValueError("Objective question is missing deterministic grade.")
                outcome = ObjectiveItemOutcome(
                    cefr_level=item.cefr_level,
                    correct=correct,
                )
                if expected_skill == "GRAMMAR":
                    grammar_outcomes.append(outcome)
                else:
                    vocabulary_outcomes.append(outcome)

            elif expected_skill == "WRITING":
                text = answer.get("text")
                if (
                    row.status != "ANSWERED"
                    or not isinstance(text, str)
                    or not text.strip()
                ):
                    raise ValueError("Required writing answer is missing.")
                writing_evidence = FrozenWritingEvidence(
                    prompt=item.body["prompt"],
                    rubric=item.body["rubric"],
                    text=text.strip(),
                )

            elif expected_skill == "SPEAKING":
                if row.status == "SKIPPED" or answer.get("skipped") is True:
                    skip_reason = answer.get("skip_reason")
                    speaking_evidence = FrozenSpeakingEvidence(
                        skipped=True,
                        skip_reason=skip_reason
                        if skip_reason
                        in ("MIC_UNAVAILABLE", "DECLINED", "TECHNICAL_ISSUE")
                        else None,
                    )
                else:
                    upload = (
                        db.scalar(
                            select(MediaUpload).where(
                                MediaUpload.id == row.media_upload_id,
                                MediaUpload.user_id == attempt.user_id,
                            )
                        )
                        if row.media_upload_id is not None
                        else None
                    )
                    now = datetime.now(UTC)
                    expiry = upload.delete_after if upload is not None else None
                    if expiry is not None and expiry.tzinfo is None:
                        expiry = expiry.replace(tzinfo=UTC)
                    if (
                        upload is None
                        or upload.status != "VERIFIED"
                        or upload.purpose != "ASSESSMENT"
                        or (expiry is not None and expiry <= now)
                    ):
                        speaking_evidence = FrozenSpeakingEvidence(
                            skipped=False,
                            prompt=item.body["prompt"],
                            rubric=item.body["rubric"],
                        )
                    else:
                        speaking_evidence = FrozenSpeakingEvidence(
                            skipped=False,
                            prompt=item.body["prompt"],
                            rubric=item.body["rubric"],
                            object_key=upload.object_key,
                            content_type=upload.content_type,
                            size_bytes=upload.size_bytes or upload.expected_size_bytes,
                            checksum_sha256=upload.checksum_sha256,
                        )

        if writing_evidence is None or speaking_evidence is None:
            raise ValueError("Missing writing or speaking evidence.")

        return FrozenAssessment(
            job_id=job.id,
            attempt_id=attempt.id,
            user_id=attempt.user_id,
            grammar_outcomes=grammar_outcomes,
            vocabulary_outcomes=vocabulary_outcomes,
            writing=writing_evidence,
            speaking=speaking_evidence,
        )


def evaluate_assessment(
    job_id: UUID,
    report_stage: Callable[[str], None] | None = None,
) -> PublicPlacement:
    """Execute the LangGraph assessment pipeline and return a validated PublicPlacement."""
    evidence = load_frozen_assessment(job_id)
    run_id, trace_config = build_assessment_trace_config(
        job_id=evidence.job_id,
        attempt_id=evidence.attempt_id,
    )
    graph = build_assessment_graph()
    final_state = graph.invoke(
        {
            "evidence": evidence,
            "report_stage": report_stage,
        },
        config=trace_config,
    )
    placement = PublicPlacement.model_validate(final_state["placement"])
    placement._langsmith_run_id = str(run_id)
    return placement
