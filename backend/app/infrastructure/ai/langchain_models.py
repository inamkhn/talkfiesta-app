"""Structured LLM evaluation helper backed by ChatOpenAI."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    ContentFilterFinishReasonError,
    InternalServerError,
    LengthFinishReasonError,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.infrastructure.ai.openai_audio import require_openai
from app.modules.jobs.assessment_runner import RetryableEvaluationError

logger = logging.getLogger(__name__)

_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
_SENTENCE_SPLIT_RE = re.compile(r"[.!?]+(?:\s+|$)")
_LEARNER_TAG_RE = re.compile(
    r"<learner_(?:writing|transcript)>\s*(.*?)\s*</learner_(?:writing|transcript)>",
    re.DOTALL | re.IGNORECASE,
)
_CONNECTORS = {
    "because",
    "although",
    "though",
    "while",
    "whereas",
    "however",
    "therefore",
    "moreover",
    "furthermore",
    "consequently",
    "nevertheless",
    "nonetheless",
    "recently",
    "eventually",
    "through",
    "since",
    "unless",
    "despite",
    "instead",
    "additionally",
    "specifically",
    "overall",
    "finally",
    "next",
    "also",
}
_SUBORDINATORS = {
    "because",
    "although",
    "though",
    "while",
    "whereas",
    "which",
    "that",
    "when",
    "whenever",
    "since",
    "unless",
    "if",
    "where",
    "who",
    "whom",
    "whose",
}
_INJECTION_PATTERNS = (
    "ignore previous instructions",
    "ignore all instructions",
    "disregard the rubric",
    "system prompt",
    "assign c2",
    "give me c2",
    "return json",
)


class EvaluationRefusedError(ValueError):
    """The provider declined evaluation; never fabricate learner feedback."""


def extract_prompt_and_learner_text(user_prompt: str) -> tuple[str, str]:
    """Extract (task_prompt, learner_text) from JSON or XML-delimited prompt payloads."""
    task_prompt = ""
    text = user_prompt
    try:
        parsed = json.loads(user_prompt)
        if isinstance(parsed, dict):
            task_prompt = str(parsed.get("task_prompt") or "")
            raw_learner = (
                parsed.get("learner_writing")
                or parsed.get("learner_transcript")
                or parsed.get("text")
                or user_prompt
            )
            text = str(raw_learner)
    except json.JSONDecodeError:
        pass

    tag_match = _LEARNER_TAG_RE.search(text)
    if tag_match:
        text = tag_match.group(1)
    return task_prompt.strip(), text.strip()


def is_usable_learner_evidence(text: str, *, task_prompt: str = "") -> bool:
    """Return False for empty, ultra-short, gibberish, prompt-copied, or injection text."""
    words = _WORD_RE.findall(text)
    if len(words) < 5:
        return False

    lower_words = [w.lower() for w in words]
    lower_text = " ".join(lower_words)
    if any(pat in lower_text for pat in _INJECTION_PATTERNS) and len(words) < 25:
        return False

    alpha_chars = [ch.lower() for w in lower_words for ch in w if ch.isalpha()]
    if not alpha_chars:
        return False
    vowel_ratio = sum(ch in "aeiouy" for ch in alpha_chars) / len(alpha_chars)
    if vowel_ratio < 0.15 or vowel_ratio > 0.85:
        return False

    if max(len(w) for w in lower_words) > 24:
        return False

    unique_ratio = len(set(lower_words)) / len(lower_words)
    if len(lower_words) >= 6 and unique_ratio < 0.25:
        return False

    if task_prompt:
        prompt_words = [w.lower() for w in _WORD_RE.findall(task_prompt)]
        if len(prompt_words) >= 5:
            overlap = sum(1 for w in lower_words if w in set(prompt_words))
            if (
                overlap / len(lower_words) >= 0.85
                and len(lower_words) <= len(prompt_words) * 1.25
            ):
                return False

    return True


def _local_fallback_evaluation[SchemaT: BaseModel](
    schema: type[SchemaT], *, user_prompt: str
) -> SchemaT:
    """Grounded, non-hallucinating linguistic evaluation when OpenAI is unavailable locally."""
    task_prompt, text = extract_prompt_and_learner_text(user_prompt)

    if not is_usable_learner_evidence(text, task_prompt=task_prompt):
        return schema.model_validate(
            {
                "sufficient_evidence": False,
                "cefr_level": None,
                "reason": "INSUFFICIENT_EVIDENCE",
                "criteria": None,
                "strengths": [],
                "improvement_priorities": [],
            }
        )

    words = _WORD_RE.findall(text)
    lower_words = [w.lower() for w in words]
    word_count = len(lower_words)
    unique_words = set(lower_words)
    unique_count = len(unique_words)
    ttr = unique_count / max(1, word_count)

    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    sentence_count = max(1, len(sentences))
    avg_sentence_len = word_count / sentence_count

    used_connectors = sorted(w for w in unique_words if w in _CONNECTORS)
    used_subordinators = sorted(w for w in unique_words if w in _SUBORDINATORS)
    advanced_words = sorted(
        {w for w in lower_words if len(w) >= 8 and w not in _CONNECTORS}
    )

    # Detect concrete surface grammar / mechanics issues present in the text
    mechanics_issues: list[str] = []
    if re.search(r"(?<![A-Za-z])i(?![A-Za-z])", text):
        mechanics_issues.append("capitalize the pronoun 'I'")
    if "alot" in unique_words:
        mechanics_issues.append("write 'a lot' as two words instead of 'alot'")
    if re.search(r"\b(?:have|has|had)\s+practice\b", text.lower()):
        mechanics_issues.append(
            "use the past participle 'practiced' after 'have/has'"
        )
    if any(s[0].islower() for s in sentences if s and s[0].isalpha()):
        mechanics_issues.append("start every sentence with a capital letter")

    # 1. Grammar band (0=A1 .. 5=C2)
    if word_count < 15:
        g_idx = 0
    elif word_count < 30:
        g_idx = 1
    elif word_count < 55:
        g_idx = 2
    elif word_count < 85:
        g_idx = 3
    else:
        g_idx = 4
    if len(used_subordinators) >= 2 and avg_sentence_len >= 12 and not mechanics_issues:
        g_idx = min(4, g_idx + 1)
    if mechanics_issues:
        g_idx = max(1 if word_count >= 25 else 0, min(g_idx, 2))

    # 2. Vocabulary band
    if unique_count < 12:
        v_idx = 0
    elif unique_count < 24:
        v_idx = 1
    elif unique_count < 42 or len(advanced_words) < 3:
        v_idx = 2
    elif unique_count < 68 or len(advanced_words) < 8:
        v_idx = 3
    else:
        v_idx = 4

    # 3. Coherence band
    if sentence_count <= 1:
        c_idx = 0 if word_count < 18 else 1
    elif len(used_connectors) == 0:
        c_idx = 1 if sentence_count == 2 else 2
    elif len(used_connectors) <= 2:
        c_idx = 2 if sentence_count <= 3 else 3
    else:
        c_idx = 3 if sentence_count <= 5 else 4
    if mechanics_issues and c_idx > 2:
        c_idx = 2

    # 4. Task completion band
    if word_count < 15:
        t_idx = 0
    elif word_count < 30:
        t_idx = 1
    elif word_count < 55:
        t_idx = 2
    elif word_count < 90:
        t_idx = 3
    else:
        t_idx = 4

    overall_idx = (g_idx + v_idx + c_idx + t_idx + 2) // 4
    overall_level = _LEVELS[overall_idx]
    g_level = _LEVELS[g_idx]
    v_level = _LEVELS[v_idx]
    c_level = _LEVELS[c_idx]
    t_level = _LEVELS[t_idx]

    # Build strictly grounded feedback referencing only measured features
    if mechanics_issues:
        grammar_fb = (
            f"Constructs {sentence_count} sentence(s) ({word_count} words), "
            f"but surface accuracy is limited by: {', '.join(mechanics_issues[:2])}."
        )
    elif used_subordinators:
        grammar_fb = (
            f"Maintains consistent clause control across {sentence_count} sentences "
            f"(avg {avg_sentence_len:.0f} words/sentence) using subordinators like "
            f"{', '.join(repr(w) for w in used_subordinators[:3])}."
        )
    else:
        grammar_fb = (
            f"Uses {sentence_count} clear sentence(s) ({word_count} words total) "
            "with mostly simple clause structures."
        )

    if advanced_words:
        sample_vocab = ", ".join(repr(w) for w in advanced_words[:3])
        vocab_fb = (
            f"Uses {unique_count} distinct words ({ttr:.0%} lexical variety), "
            f"including specific terms such as {sample_vocab}."
        )
    else:
        vocab_fb = (
            f"Uses {unique_count} distinct words across {word_count} total words "
            "relying primarily on high-frequency everyday vocabulary."
        )

    if used_connectors:
        sample_conn = ", ".join(repr(w) for w in used_connectors[:3])
        coherence_fb = (
            f"Links ideas across {sentence_count} sentence(s) using discourse markers "
            f"such as {sample_conn}."
        )
    else:
        coherence_fb = (
            f"Presents {sentence_count} sentence(s) in sequence with minimal explicit "
            "transition markers between ideas."
        )

    task_fb = (
        f"Provides a {word_count}-word response across {sentence_count} sentence(s) "
        f"demonstrating {t_level}-level task development."
    )

    strengths: list[str] = []
    if advanced_words:
        strengths.append(
            f"Uses relevant topic vocabulary ({', '.join(advanced_words[:3])}) to explain the experience"
        )
    if used_connectors:
        strengths.append(
            f"Connects ideas with clear transitions ({', '.join(used_connectors[:3])})"
        )
    if not mechanics_issues and sentence_count >= 3:
        strengths.append(
            f"Maintains clean sentence punctuation and capitalization across {sentence_count} sentences"
        )
    if not strengths:
        strengths.append(
            f"Communicates a direct {word_count}-word response addressing the prompt"
        )

    priorities: list[str] = []
    for issue in mechanics_issues[:2]:
        priorities.append(f"Proofread mechanics: {issue}")
    if len(used_connectors) < 2:
        priorities.append(
            "Add explicit linking words (e.g., 'however', 'therefore', 'while') between sentences"
        )
    if len(used_subordinators) < 2:
        priorities.append(
            "Combine short clauses into complex sentences using 'because', 'although', or 'which'"
        )
    if word_count < 60:
        priorities.append(
            "Expand the response with concrete examples and outcome details (aim for 60–90 words)"
        )
    if not priorities:
        priorities.append(
            "Vary sentence openings and incorporate more nuanced academic phrasing to reach C1"
        )

    return schema.model_validate(
        {
            "sufficient_evidence": True,
            "cefr_level": overall_level,
            "reason": None,
            "criteria": {
                "grammar": {"level": g_level, "feedback": grammar_fb},
                "vocabulary": {"level": v_level, "feedback": vocab_fb},
                "coherence": {"level": c_level, "feedback": coherence_fb},
                "task_completion": {"level": t_level, "feedback": task_fb},
            },
            "strengths": strengths[:4],
            "improvement_priorities": priorities[:4],
        }
    )


def invoke_structured_model[SchemaT: BaseModel](
    schema: type[SchemaT],
    *,
    system_prompt: str,
    user_prompt: str,
    runnable_config: RunnableConfig | None = None,
    max_output_tokens: int | None = None,
    usage_callback: Callable[[dict], None] | None = None,
    allow_local_fallback: bool = True,
) -> SchemaT:
    """Run one structured-output call; job execution owns retry limits."""
    if allow_local_fallback and not settings.openai_api_key.strip() and settings.environment == "local":
        return _local_fallback_evaluation(schema, user_prompt=user_prompt)
    require_openai()
    llm = ChatOpenAI(
        model=settings.openai_evaluation_model,
        api_key=settings.openai_api_key,
        temperature=0,
        timeout=settings.openai_timeout_seconds,
        max_retries=0,
        **({"max_tokens": max_output_tokens} if max_output_tokens is not None else {}),
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
    except (AuthenticationError, PermissionDeniedError) as exc:
        if allow_local_fallback and settings.environment == "local":
            logger.warning(
                "openai_auth_error_using_local_fallback status=%s",
                getattr(exc, "status_code", "auth"),
            )
            return _local_fallback_evaluation(schema, user_prompt=user_prompt)
        raise
    except APIStatusError as exc:
        if allow_local_fallback and exc.status_code in (401, 403) and settings.environment == "local":
            logger.warning(
                "openai_status_error_using_local_fallback status=%s", exc.status_code
            )
            return _local_fallback_evaluation(schema, user_prompt=user_prompt)
        if exc.status_code >= 500 or exc.status_code in (408, 409, 429):
            raise RetryableEvaluationError("OpenAI evaluation unavailable.") from exc
        raise
    except ContentFilterFinishReasonError:
        raise EvaluationRefusedError("Language evaluation was declined.") from None
    except Exception as exc:
        # langchain_openai wraps openai.AuthenticationError into OpenAIAuthenticationError
        if allow_local_fallback and settings.environment == "local" and (
            "401" in str(exc)
            or "api key" in str(exc).lower()
            or "authentication" in type(exc).__name__.lower()
        ):
            logger.warning(
                "openai_client_auth_fallback error_type=%s", type(exc).__name__
            )
            return _local_fallback_evaluation(schema, user_prompt=user_prompt)
        raise
    raw = result.get("raw")
    if usage_callback is not None:
        usage_callback(getattr(raw, "usage_metadata", None) or {})
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
