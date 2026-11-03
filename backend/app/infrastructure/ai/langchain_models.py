"""Structured LLM evaluation helper backed by ChatOpenAI."""

from __future__ import annotations

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


def invoke_structured_model[SchemaT: BaseModel](
    schema: type[SchemaT],
    *,
    system_prompt: str,
    user_prompt: str,
    runnable_config: RunnableConfig | None = None,
) -> SchemaT:
    """Run one structured-output call; job execution owns retry limits."""
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
