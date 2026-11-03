"""Private, bounded audio-to-text step; storage/provider work holds no DB transaction."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.exceptions import (
    ConflictError,
    ServiceUnavailableError,
    ValidationAppError,
)
from app.infrastructure.ai.openai_audio import transcribe_audio_bytes
from app.infrastructure.storage.s3 import read_audio
from app.modules.assessment.ai.state import FrozenSpeakingEvidence
from app.modules.jobs.assessment_runner import RetryableEvaluationError


class SpeakingTranscript(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    text: str | None = Field(max_length=20000, repr=False)
    reason: (
        Literal[
            "MIC_UNAVAILABLE",
            "DECLINED",
            "TECHNICAL_ISSUE",
            "NOT_ASSESSED",
            "AUDIO_UNAVAILABLE",
            "INSUFFICIENT_EVIDENCE",
        ]
        | None
    )

    @model_validator(mode="after")
    def require_text_or_reason(self):
        if self.reason is None:
            if self.text is None or not self.text.strip():
                raise ValueError("Usable transcription requires text.")
        elif self.text is not None:
            raise ValueError("Unavailable transcription must not contain text.")
        return self


def _expired(evidence: FrozenSpeakingEvidence) -> bool:
    # A missing/naive retention deadline is not trusted audio evidence.
    return (
        evidence.delete_after is None
        or evidence.delete_after.tzinfo is None
        or evidence.delete_after <= datetime.now(UTC)
    )


def transcribe_speaking_audio(
    evidence: FrozenSpeakingEvidence,
    report_stage: Callable[[str], None] | None = None,
) -> SpeakingTranscript:
    if evidence.skipped:
        return SpeakingTranscript(
            text=None, reason=evidence.skip_reason or "NOT_ASSESSED"
        )
    if (
        not evidence.object_key
        or not evidence.content_type
        or not evidence.size_bytes
        or not evidence.checksum_sha256
        or _expired(evidence)
    ):
        return SpeakingTranscript(text=None, reason="AUDIO_UNAVAILABLE")

    if report_stage is not None:
        report_stage("TRANSCRIBING_AUDIO")
    try:
        data = read_audio(
            evidence.object_key,
            evidence.content_type,
            evidence.size_bytes,
            evidence.checksum_sha256,
        )
    except ConflictError as exc:
        if exc.code != "UPLOAD_NOT_FOUND":
            raise
        return SpeakingTranscript(text=None, reason="AUDIO_UNAVAILABLE")
    except ValidationAppError:
        return SpeakingTranscript(text=None, reason="AUDIO_UNAVAILABLE")
    except ServiceUnavailableError as exc:
        raise RetryableEvaluationError(
            "Audio storage temporarily unavailable."
        ) from exc

    if _expired(evidence):
        return SpeakingTranscript(text=None, reason="AUDIO_UNAVAILABLE")
    # Recheck the worker claim after downloading and before a paid provider call.
    if report_stage is not None:
        report_stage("TRANSCRIBING_AUDIO")
    text = transcribe_audio_bytes(data, evidence.content_type)
    # Minimal usability gate, not a proficiency score or a silence detector.
    if sum(any(char.isalpha() for char in word) for word in text.split()) < 3:
        return SpeakingTranscript(text=None, reason="INSUFFICIENT_EVIDENCE")
    return SpeakingTranscript(text=text, reason=None)
