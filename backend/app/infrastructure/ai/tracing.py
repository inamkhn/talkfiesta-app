"""Sanitized LangSmith tracing configuration and PII/learner-text redaction."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID, uuid4

from langchain_core.runnables import RunnableConfig
from langchain_core.tracers.langchain import LangChainTracer
from langsmith import Client

from app.core.config import settings

REDACTED_LEARNER_TEXT = "[REDACTED_LEARNER_TEXT]"
REDACTED_PII = "[REDACTED_PII]"

_LEARNER_BLOCK_RE = re.compile(
    r"<(learner_writing|learner_transcript)>.*?</\1>",
    flags=re.DOTALL | re.IGNORECASE,
)
_SENSITIVE_KEYS = frozenset(
    {
        "text",
        "transcript",
        "audio",
        "audio_bytes",
        "password",
        "email",
        "authorization",
        "cookie",
        "token",
    }
)


def sanitize_trace_payload(value: Any) -> Any:
    """Recursively scrub learner writing, transcripts, and PII from trace inputs/outputs."""
    if not settings.langsmith_redact_learner_text:
        return value
    if isinstance(value, str):
        return _LEARNER_BLOCK_RE.sub(
            lambda m: f"<{m.group(1)}>{REDACTED_LEARNER_TEXT}</{m.group(1)}>",
            value,
        )
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for k, v in value.items():
            key_lower = str(k).lower()
            if key_lower in ("text", "transcript"):
                sanitized[k] = REDACTED_LEARNER_TEXT
            elif key_lower in _SENSITIVE_KEYS:
                sanitized[k] = REDACTED_PII
            else:
                sanitized[k] = sanitize_trace_payload(v)
        return sanitized
    if isinstance(value, list):
        return [sanitize_trace_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_trace_payload(item) for item in value)
    return value


def build_assessment_trace_config(
    *,
    job_id: UUID,
    attempt_id: UUID,
    run_id: UUID | None = None,
) -> tuple[UUID, RunnableConfig]:
    """Build a LangGraph/LangChain RunnableConfig with safe operational metadata and redaction."""
    trace_run_id = run_id or uuid4()
    metadata = {
        "job_id": str(job_id),
        "attempt_id": str(attempt_id),
        "rubric_version": settings.assessment_rubric_version,
        "model": settings.openai_evaluation_model,
        "environment": settings.environment,
    }
    callbacks: list[ Any ] = []
    if settings.langsmith_tracing_enabled and settings.langsmith_api_key:
        client = Client(
            api_url=settings.langsmith_endpoint,
            api_key=settings.langsmith_api_key,
            hide_inputs=sanitize_trace_payload,
            hide_outputs=sanitize_trace_payload,
        )
        callbacks.append(
            LangChainTracer(
                project_name=settings.langsmith_project,
                client=client,
            )
        )
    config: RunnableConfig = {
        "run_id": trace_run_id,
        "run_name": "talkfiesta.initial_assessment",
        "tags": ["assessment", settings.assessment_rubric_version],
        "metadata": metadata,
        "callbacks": callbacks,
    }
    return trace_run_id, config

