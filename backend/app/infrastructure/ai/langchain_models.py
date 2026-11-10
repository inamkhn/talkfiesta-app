"""Structured LLM evaluation helper backed by ChatOpenAI."""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
    ContentFilterFinishReasonError,
    InternalServerError,
    LengthFinishReasonError,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.infrastructure.ai.openai_audio import require_openai
from app.modules.jobs.assessment_runner import RetryableEvaluationError


class EvaluationRefusedError(ValueError):
    """The provider declined evaluation; never fabricate learner feedback."""


def _local_fallback_evaluation[SchemaT: BaseModel](
    schema: type[SchemaT], *, user_prompt: str
) -> SchemaT:
    """Deterministic local evaluation fallback when OPENAI_API_KEY is not configured."""
    text = user_prompt
    try:
        parsed_prompt = json.loads(user_prompt)
        if isinstance(parsed_prompt, dict):
            text = str(
                parsed_prompt.get("learner_writing")
                or parsed_prompt.get("learner_transcript")
                or user_prompt
            )
    except json.JSONDecodeError:
        pass

    words = [w for w in text.split() if any(ch.isalpha() for ch in w)]
    word_count = len(words)
    if word_count < 15:
        level = "A1"
    elif word_count < 30:
        level = "A2"
    elif word_count < 60:
        level = "B1"
    elif word_count < 100:
        level = "B2"
    else:
        level = "C1"

    return schema.model_validate(
        {
            "sufficient_evidence": True,
            "cefr_level": level,
            "reason": None,
            "criteria": {
                "grammar": {
                    "level": level,
                    "feedback": f"Demonstrates {level}-level sentence control and clause accuracy.",
                },
                "vocabulary": {
                    "level": level,
                    "feedback": f"Uses appropriate {level} vocabulary to address the prompt.",
                },
                "coherence": {
                    "level": level,
                    "feedback": "Organizes ideas logically with clear progression.",
                },
                "task_completion": {
                    "level": level,
                    "feedback": "Directly addresses the prompt requirements.",
                },
            },
            "strengths": [
                "Communicates key ideas clearly and directly",
                f"Maintains consistent {level} vocabulary and sentence flow",
            ],
            "improvement_priorities": [
                "Use a wider range of linking expressions between ideas",
                "Incorporate more varied complex sentence structures",
            ],
        }
    )


def invoke_structured_model[SchemaT: BaseModel](
    schema: type[SchemaT],
    *,
    system_prompt: str,
    user_prompt: str,
    runnable_config: RunnableConfig | None = None,
) -> SchemaT:
    """Run one structured-output call; job execution owns retry limits."""
    if not settings.openai_api_key.strip() and settings.environment == "local":
        return _local_fallback_evaluation(schema, user_prompt=user_prompt)
    require_openai()
    llm = ChatOpenAI(
        model=settings.openai_evaluation_model,
        api_key=settings.openai_api_key,
        temperature=0,
        timeout=settings.openai_timeout_seconds,
        max_retries=0,
    ).with_structured_output(
        schema, method="json_schema", strict=True, include_raw=True
    )
    try:
        result = llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ],
            config=runnable_config,
        )
    except (
        APIConnectionError,
        APITimeoutError,
        RateLimitError,
        InternalServerError,
        APIResponseValidationError,
        LengthFinishReasonError,
    ) as exc:
        raise RetryableEvaluationError("OpenAI evaluation transient error.") from exc
    except APIStatusError as exc:
        if exc.status_code >= 500 or exc.status_code in (408, 409, 429):
            raise RetryableEvaluationError("OpenAI evaluation unavailable.") from exc
        raise
    except ContentFilterFinishReasonError:
        raise EvaluationRefusedError("Language evaluation was declined.") from None
    raw = result.get("raw")
    if (
        getattr(raw, "additional_kwargs", {}).get("refusal")
        or getattr(raw, "response_metadata", {}).get("finish_reason")
        == "content_filter"
        or type(result.get("parsing_error")).__name__ == "OpenAIRefusalError"
    ):
        raise EvaluationRefusedError("Language evaluation was declined.")
    if result.get("parsing_error") is not None or result.get("parsed") is None:
        raise RetryableEvaluationError("Language evaluation output was invalid.")
    parsed = result["parsed"]
    try:
        return schema.model_validate(
            parsed.model_dump() if isinstance(parsed, BaseModel) else parsed
        )
    except ValidationError:
        raise RetryableEvaluationError(
            "Language evaluation output was invalid."
        ) from None
