"""OpenAI audio transcription wrapper with transient error classification."""

from __future__ import annotations

import io
from functools import lru_cache

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

from app.core.config import settings
from app.modules.jobs.assessment_runner import RetryableEvaluationError

_EXTENSIONS = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
}


def require_openai() -> None:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")


@lru_cache
def openai_client() -> OpenAI:
    require_openai()
    return OpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.openai_timeout_seconds,
        max_retries=0,
    )


def transcribe_audio_bytes(data: bytes, content_type: str) -> str:
    """Transcribe verified audio bytes into plain text."""
    ext = _EXTENSIONS.get(content_type, "webm")
    buffer = io.BytesIO(data)
    buffer.name = f"recording.{ext}"
    try:
        response = openai_client().audio.transcriptions.create(
            model=settings.openai_transcription_model,
            file=(buffer.name, buffer, content_type),
        )
    except (
        APIConnectionError,
        APITimeoutError,
        RateLimitError,
        InternalServerError,
    ) as exc:
        raise RetryableEvaluationError("OpenAI transcription transient error.") from exc
    except APIStatusError as exc:
        if exc.status_code >= 500 or exc.status_code == 429:
            raise RetryableEvaluationError(
                "OpenAI transcription unavailable."
            ) from exc
        raise
    text = getattr(response, "text", None)
    return text.strip() if isinstance(text, str) else ""

