"""LangGraph workflow for generating, validating, and reviewing one Vocabulary day unit."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.infrastructure.ai.langchain_models import invoke_structured_model
from app.modules.content.blueprint_loader import ResolvedDayContext
from app.modules.content.contracts import AiReviewReport, VocabularyUnitOutput
from app.modules.content.prompt_loader import (
    load_generator_prompt,
    load_reviewer_prompt,
)
from app.modules.content.validators import validate_vocabulary_unit


class VocabGenerationState(TypedDict, total=False):
    job_id: str
    generation_batch_key: str
    release_key: str
    prompt_bundle_version: str
    context: ResolvedDayContext
    prior_words: list[str]
    unit: VocabularyUnitOutput | None
    validation_errors: list[str]
    validation_warnings: list[str]
    review_report: AiReviewReport | None
    feedback_for_retry: list[str]
    retry_count: int
    max_retries: int
    outcome: Literal["PASS_TO_REVIEW", "NEEDS_EDITOR_REVIEW", "FAILED"]
    _should_regenerate: bool
    report_stage: Callable[[str], None] | None
    invoke_model: Callable[..., Any] | None
    invoke_model: Callable | None


def _build_generation_payload(state: VocabGenerationState) -> str:
    ctx = state["context"]
    payload = {
        "cefr_level": ctx.cefr_level,
        "cycle": ctx.cycle,
        "day": ctx.day,
        "goal_variant": ctx.goal_variant,
        "goal_day_focus": ctx.goal_day_focus,
        "register": ctx.goal_guidance.language_register,
        "theme": ctx.day_blueprint.theme,
        "learning_objective": ctx.day_blueprint.learning_objective,
        "grammar_focus": ctx.day_blueprint.grammar_focus,
        "vocabulary_theme": ctx.day_blueprint.vocabulary_theme.model_dump(mode="json"),
        "prior_day_summaries": [
            s.model_dump(mode="json") for s in ctx.prior_day_summaries
        ],
        "prior_words": state.get("prior_words", []),
        "validation_feedback": state.get("feedback_for_retry", []),
    }
    return json.dumps(payload, ensure_ascii=False)


def _generate_node(
    state: VocabGenerationState, config: RunnableConfig | None = None
) -> dict:
    report_stage = state.get("report_stage")
    if report_stage is not None:
        report_stage("GENERATING_CONTENT")

    _, system_prompt = load_generator_prompt(
        "VOCABULARY",
        prompt_bundle_version=state.get("prompt_bundle_version", "content-factory-v1"),
    )
    unit = (state.get("invoke_model") or invoke_structured_model)(
        VocabularyUnitOutput,
        system_prompt=system_prompt,
        user_prompt=_build_generation_payload(state),
        runnable_config=config,
    )
    return {
        "unit": unit,
        "validation_errors": [],
        "validation_warnings": [],
        "_should_regenerate": False,
    }


def _validate_node(state: VocabGenerationState) -> dict:
    report_stage = state.get("report_stage")
    if report_stage is not None:
        report_stage("VALIDATING_CONTENT")

    unit = state["unit"]
    assert unit is not None
    ctx = state["context"]
    prior = set(state.get("prior_words", []))

    validation = validate_vocabulary_unit(unit, ctx.day_blueprint, prior_words=prior)
    errors = [f"[{i.code}] {i.field}: {i.message}" for i in validation.errors]
    warnings = [f"[{i.code}] {i.field}: {i.message}" for i in validation.warnings]

    if errors:
        retries = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 2)
        if retries < max_retries:
            return {
                "validation_errors": errors,
                "validation_warnings": warnings,
                "feedback_for_retry": errors,
                "retry_count": retries + 1,
            }
        return {
            "validation_errors": errors,
            "validation_warnings": warnings,
            "outcome": "FAILED",
        }

    return {
        "validation_errors": [],
        "validation_warnings": warnings,
    }


def _route_after_validation(
    state: VocabGenerationState,
) -> Literal["generate_content", "review_quality", "__end__"]:
    if state.get("outcome") == "FAILED":
        return "__end__"
    if state.get("validation_errors"):
        return "generate_content"
    return "review_quality"


def _review_node(
    state: VocabGenerationState, config: RunnableConfig | None = None
) -> dict:
    report_stage = state.get("report_stage")
    if report_stage is not None:
        report_stage("REVIEWING_QUALITY")

    unit = state["unit"]
    assert unit is not None
    ctx = state["context"]

    _, reviewer_prompt = load_reviewer_prompt(
        "VOCABULARY",
        prompt_bundle_version=state.get("prompt_bundle_version", "content-factory-v1"),
    )
    review_payload = json.dumps(
        {
            "cefr_level": ctx.cefr_level,
            "goal_variant": ctx.goal_variant,
            "day_blueprint": ctx.day_blueprint.model_dump(mode="json"),
            "deterministic_warnings": state.get("validation_warnings", []),
            "generated_unit": unit.model_dump(mode="json"),
        },
        ensure_ascii=False,
    )
    report = (state.get("invoke_model") or invoke_structured_model)(
        AiReviewReport,
        system_prompt=reviewer_prompt,
        user_prompt=review_payload,
        runnable_config=config,
    )

    retries = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)
    if (
        report.overall_decision == "REGENERATE" or report.critical_issues
    ) and retries < max_retries:
        feedback = list(report.critical_issues) or [report.recommended_action]
        return {
            "review_report": report,
            "feedback_for_retry": feedback,
            "retry_count": retries + 1,
            "_should_regenerate": True,
        }

    if (
        report.meets_auto_review_bar()
        and report.overall_decision == "PASS_TO_HUMAN_REVIEW"
    ):
        return {
            "review_report": report,
            "outcome": "PASS_TO_REVIEW",
            "_should_regenerate": False,
        }

    return {
        "review_report": report,
        "outcome": "NEEDS_EDITOR_REVIEW",
        "_should_regenerate": False,
    }


def _route_after_review_clean(
    state: VocabGenerationState,
) -> Literal["generate_content", "__end__"]:
    if state.get("_should_regenerate"):
        return "generate_content"
    return "__end__"


def build_vocab_generation_graph():
    """Compile the bounded LangGraph workflow for one Vocabulary day unit."""
    graph = StateGraph(VocabGenerationState)
    graph.add_node("generate_content", _generate_node)
    graph.add_node("validate_rules", _validate_node)
    graph.add_node("review_quality", _review_node)

    graph.add_edge(START, "generate_content")
    graph.add_edge("generate_content", "validate_rules")
    graph.add_conditional_edges(
        "validate_rules",
        _route_after_validation,
        {
            "generate_content": "generate_content",
            "review_quality": "review_quality",
            "__end__": END,
        },
    )
    graph.add_conditional_edges(
        "review_quality",
        _route_after_review_clean,
        {
            "generate_content": "generate_content",
            "__end__": END,
        },
    )
    return graph.compile()
