"""Structured LLM evaluation helper backed by ChatOpenAI."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)
from pydantic import BaseModel

from app.core.config import settings
from app.infrastructure.ai.openai_audio import require_openai
from app.modules.jobs.assessment_runner import RetryableEvaluationError


def invoke_structured_model[SchemaT: BaseModel](
    schema: type[SchemaT],
    *,
    system_prompt: str,
    user_prompt: str,
    runnable_config: RunnableConfig | None = None,
) -> SchemaT:
    """Run a deterministic structured-output evaluation call."""
    require_openai()
    llm = ChatOpenAI(
        model=settings.openai_evaluation_model,
        api_key=settings.openai_api_key,
        temperature=0,
        timeout=settings.openai_timeout_seconds,
        max_retries=0,
    ).with_structured_output(schema, strict=True)
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
    ) as exc:
        raise RetryableEvaluationError("OpenAI evaluation transient error.") from exc
    except APIStatusError as exc:
        if exc.status_code >= 500 or exc.status_code == 429:
            raise RetryableEvaluationError("OpenAI evaluation unavailable.") from exc
        raise
    return schema.model_validate(
        result.model_dump() if isinstance(result, BaseModel) else result
    )
