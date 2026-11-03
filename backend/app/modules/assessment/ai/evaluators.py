"""Evaluate the worker's validated snapshot without reloading database state."""

import json
from collections.abc import Callable

from app.infrastructure.ai.tracing import build_assessment_trace_config
from app.modules.assessment.ai.checkpoints import CheckpointStore
from app.modules.assessment.ai.evidence import AssessmentEvidence
from app.modules.assessment.ai.graph import build_assessment_graph
from app.modules.assessment.ai.schemas import (
    AssessmentEvaluation,
    PlacementResult,
    ResponseEvaluation,
)
from app.modules.assessment.ai.state import (
    FrozenAssessment,
    FrozenSpeakingEvidence,
    FrozenWritingEvidence,
)
from app.modules.assessment.placement_policy import ObjectiveItemOutcome
from app.modules.assessment.schemas import PublicPlacement
from app.modules.jobs.assessment_runner import JobClaim


def graph_evidence(snapshot: AssessmentEvidence) -> FrozenAssessment:
    """Project trusted evidence into the graph; no database reads or private keys."""
    writing = next(q for q in snapshot.questions if q.skill == "WRITING")
    speaking = next(q for q in snapshot.questions if q.skill == "SPEAKING")
    audio = speaking.audio
    skip_reason = speaking.speaking_unassessed_reason
    explicitly_skipped = skip_reason in (
        "MIC_UNAVAILABLE",
        "DECLINED",
        "TECHNICAL_ISSUE",
    )
    return FrozenAssessment(
        job_id=snapshot.job_id,
        attempt_id=snapshot.assessment_id,
        grammar_outcomes=[
            ObjectiveItemOutcome(q.cefr_level, q.objective_correct)
            for q in snapshot.questions
            if q.skill == "GRAMMAR"
        ],
        vocabulary_outcomes=[
            ObjectiveItemOutcome(q.cefr_level, q.objective_correct)
            for q in snapshot.questions
            if q.skill == "VOCABULARY"
        ],
        writing=FrozenWritingEvidence(
            prompt=writing.prompt,
            rubric=json.loads(writing.rubric_json),
            text=writing.writing_text,
        ),
        speaking=FrozenSpeakingEvidence(
            skipped=explicitly_skipped,
            skip_reason=skip_reason if explicitly_skipped else None,
            prompt=speaking.prompt,
            rubric=json.loads(speaking.rubric_json),
            object_key=audio.object_key if audio else None,
            content_type=audio.content_type if audio else None,
            size_bytes=audio.size_bytes if audio else None,
            checksum_sha256=audio.checksum_sha256 if audio else None,
            delete_after=audio.delete_after if audio else None,
        ),
    )


def evaluate_assessment(
    snapshot: AssessmentEvidence,
    report_stage: Callable[[str], None] | None = None,
    *,
    claim: JobClaim,
) -> AssessmentEvaluation:
    evidence = graph_evidence(snapshot)
    run_id, trace_config = build_assessment_trace_config(
        job_id=evidence.job_id,
        attempt_id=evidence.attempt_id,
    )
    final_state = build_assessment_graph().invoke(
        {
            "evidence": evidence,
            "report_stage": report_stage,
            "checkpoints": CheckpointStore(claim, snapshot),
        },
        config=trace_config,
    )
    raw = final_state["placement"]
    placement = PlacementResult.model_validate(
        raw.model_dump() if isinstance(raw, PublicPlacement) else raw
    )
    result = AssessmentEvaluation(
        placement=placement,
        responses=[
            ResponseEvaluation(
                response_id=question.response_id,
                question_id=question.question_id,
                revision=question.revision,
                skill=question.skill,
                placement=getattr(placement.skills, question.skill.lower()),
                language=final_state[f"{question.skill.lower()}_evaluation"],
            )
            for question in snapshot.questions
            if question.skill in ("WRITING", "SPEAKING")
        ],
    )
    result._langsmith_run_id = str(run_id)
    return result
