"""Worker-only, detached evidence from one consistent PostgreSQL snapshot.

No provider or storage calls, logs, writes, or ORM objects leave this module.
Private question keys/rubrics must never be serialized into a learner API.
"""

import base64
import binascii
import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.infrastructure.database import model_registry  # noqa: F401
from app.infrastructure.database.sync_session import sync_engine
from app.modules.assessment.models import AssessmentAttempt, AssessmentResponse
from app.modules.assessment.schemas import (
    ChoiceAnswer,
    SaveAnswerRequest,
    SpeakingAnswer,
    WritingAnswer,
)
from app.modules.assessment.selection import SEQUENCE, valid_question
from app.modules.auth.models import User
from app.modules.content.models import ContentItem
from app.modules.jobs.assessment_runner import LostClaimError
from app.modules.jobs.models import AiJob
from app.modules.media.models import MediaUpload

ANSWER_ADAPTER = TypeAdapter(SaveAnswerRequest)
AUDIO_TYPES = {"audio/webm", "audio/ogg", "audio/wav", "audio/mpeg", "audio/mp4"}


class InvalidEvidenceError(ValueError):
    """Required frozen evidence is inconsistent; message never contains learner data."""


@dataclass(frozen=True)
class AudioEvidence:
    upload_id: UUID
    object_key: str = field(repr=False)
    content_type: str
    size_bytes: int
    checksum_sha256: str = field(repr=False)
    duration_seconds: Decimal
    delete_after: datetime


@dataclass(frozen=True)
class QuestionEvidence:
    response_id: UUID
    question_id: UUID
    position: int
    revision: int
    content_version: int
    skill: str
    kind: str
    cefr_level: str | None
    prompt: str = field(repr=False)
    # Immutable JSON/tuples keep nested evidence from being mutated by graph nodes.
    rubric_json: str | None = field(default=None, repr=False)
    choices: tuple[tuple[str, str], ...] = field(default=(), repr=False)
    selected_choice_id: str | None = field(default=None, repr=False)
    correct_choice_id: str | None = field(default=None, repr=False)
    objective_correct: bool | None = None
    writing_text: str | None = field(default=None, repr=False)
    audio: AudioEvidence | None = field(default=None, repr=False)
    speaking_unassessed_reason: str | None = None


@dataclass(frozen=True)
class AssessmentEvidence:
    job_id: UUID
    assessment_id: UUID
    content_release: str
    submitted_at: datetime
    questions: tuple[QuestionEvidence, ...] = field(repr=False)


def _audio(
    db: Session,
    row: AssessmentResponse,
    answer: SpeakingAnswer,
    user_id: UUID,
    now: datetime,
) -> AudioEvidence | None:
    if row.media_upload_id is None:
        # The FK uses SET NULL when retention deletes the media record.
        return None
    if row.media_upload_id != answer.media_upload_id:
        raise InvalidEvidenceError("Speaking audio binding is inconsistent.")
    upload = db.get(MediaUpload, row.media_upload_id)
    # Optional speech may become unavailable through retention after submission.
    if upload is None:
        return None
    if (
        upload.user_id != user_id
        or upload.assessment_response_id != row.id
        or upload.purpose != "ASSESSMENT"
    ):
        raise InvalidEvidenceError("Speaking audio ownership is inconsistent.")
    if (
        upload.status != "VERIFIED"
        or upload.verified_at is None
        or upload.delete_after is None
        or upload.delete_after <= now
        or upload.content_type not in AUDIO_TYPES
        or upload.size_bytes is None
        or not 0 < upload.size_bytes <= settings.audio_max_bytes
        or upload.expected_size_bytes != upload.size_bytes
        or upload.duration_seconds is None
        or not upload.duration_seconds.is_finite()
        or not Decimal("0.5")
        <= upload.duration_seconds
        <= settings.audio_max_duration_seconds
        or not upload.object_key
    ):
        return None
    try:
        checksum = base64.b64decode(upload.checksum_sha256 or "", validate=True)
    except binascii.Error:
        return None
    if (
        len(checksum) != 32
        or base64.b64encode(checksum).decode() != upload.checksum_sha256
    ):
        return None
    return AudioEvidence(
        upload_id=upload.id,
        object_key=upload.object_key,
        content_type=upload.content_type,
        size_bytes=upload.size_bytes,
        checksum_sha256=upload.checksum_sha256,
        duration_seconds=upload.duration_seconds,
        delete_after=upload.delete_after,
    )


def _question(
    db: Session,
    row: AssessmentResponse,
    item: ContentItem,
    user_id: UUID,
    now: datetime,
) -> QuestionEvidence:
    if (
        row.status not in ("ANSWERED", "SKIPPED")
        or row.answered_at is None
        or row.revision < 1
        or not isinstance(row.answer, dict)
    ):
        raise InvalidEvidenceError("An assessment answer is not finalized.")
    try:
        answer = ANSWER_ADAPTER.validate_python(
            {**row.answer, "expected_revision": row.revision}
        )
    except ValidationError:
        raise InvalidEvidenceError("A stored answer is invalid.") from None
    if answer.kind != item.body["kind"]:
        raise InvalidEvidenceError("Answer kind does not match its question.")
    values = {
        "response_id": row.id,
        "question_id": item.id,
        "position": row.position,
        "revision": row.revision,
        "content_version": item.content_version,
        "skill": item.body["skill"],
        "kind": answer.kind,
        "cefr_level": item.cefr_level,
        "prompt": item.body["prompt"],
    }
    if isinstance(answer, ChoiceAnswer):
        ids = {choice["id"] for choice in item.body["choices"]}
        correct = answer.selected_choice_id == item.body["correct_choice_id"]
        grade = row.grading.get("correct") if isinstance(row.grading, dict) else None
        if (
            row.status != "ANSWERED"
            or answer.selected_choice_id not in ids
            or type(grade) is not bool
            or grade != correct
            or row.media_upload_id is not None
        ):
            raise InvalidEvidenceError("Objective answer or grading is inconsistent.")
        return QuestionEvidence(
            **values,
            choices=tuple((c["id"], c["text"]) for c in item.body["choices"]),
            selected_choice_id=answer.selected_choice_id,
            correct_choice_id=item.body["correct_choice_id"],
            objective_correct=correct,
        )
    try:
        rubric = json.dumps(item.body["rubric"], ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError):
        raise InvalidEvidenceError("Question rubric is invalid.") from None
    if len(rubric) > 64000:
        raise InvalidEvidenceError("Question rubric exceeds the evidence limit.")
    if isinstance(answer, WritingAnswer):
        if (
            not answer.finalize
            or row.status != "ANSWERED"
            or row.media_upload_id is not None
        ):
            raise InvalidEvidenceError("Required writing evidence is not finalized.")
        return QuestionEvidence(**values, rubric_json=rubric, writing_text=answer.text)
    if answer.skipped:
        if row.status != "SKIPPED" or row.media_upload_id is not None:
            raise InvalidEvidenceError("Speaking skip is inconsistent.")
        return QuestionEvidence(
            **values, rubric_json=rubric, speaking_unassessed_reason=answer.skip_reason
        )
    if row.status != "ANSWERED":
        raise InvalidEvidenceError("Speaking evidence is not finalized.")
    audio = _audio(db, row, answer, user_id, now)
    return QuestionEvidence(
        **values,
        rubric_json=rubric,
        audio=audio,
        speaking_unassessed_reason="AUDIO_UNAVAILABLE" if audio is None else None,
    )


def load_assessment_evidence(job_id: UUID, claim_token: UUID) -> AssessmentEvidence:
    """Read one snapshot for the owning execution; close it before any AI work.

    A live claim token is mandatory. The runner still fences stage/result writes
    because the claim can expire after this snapshot has been loaded.
    """
    with (
        sync_engine.connect().execution_options(
            isolation_level="REPEATABLE READ"
        ) as connection,
        Session(bind=connection) as db,
        db.begin(),
    ):
        db.execute(text("SET TRANSACTION READ ONLY"))
        now = db.scalar(select(func.clock_timestamp()))
        job = db.get(AiJob, job_id)
        if (
            job is None
            or job.job_type != "ASSESSMENT"
            or job.status != "RUNNING"
            or job.claim_token != claim_token
            or job.lease_expires_at is None
            or job.lease_expires_at <= now
        ):
            raise LostClaimError()
        user = db.get(User, job.user_id) if job.user_id else None
        attempt = (
            db.get(AssessmentAttempt, job.assessment_attempt_id)
            if job.assessment_attempt_id
            else None
        )
        if (
            user is None
            or not user.is_active
            or attempt is None
            or attempt.user_id != user.id
            or attempt.kind != "INITIAL"
            or attempt.status != "PROCESSING"
            or attempt.submitted_at is None
        ):
            raise InvalidEvidenceError("Assessment is not eligible for evaluation.")
        rows = list(
            db.scalars(
                select(AssessmentResponse)
                .where(AssessmentResponse.assessment_attempt_id == attempt.id)
                .order_by(AssessmentResponse.position)
            )
        )
        if (
            len(rows) != len(SEQUENCE)
            or [r.position for r in rows] != list(range(1, len(SEQUENCE) + 1))
            or len({r.question_content_id for r in rows}) != len(rows)
        ):
            raise InvalidEvidenceError(
                "Assessment assignments are incomplete or inconsistent."
            )
        items = {
            item.id: item
            for item in db.scalars(
                select(ContentItem).where(
                    ContentItem.id.in_([r.question_content_id for r in rows])
                )
            )
        }
        evidence = []
        for row, skill in zip(rows, SEQUENCE, strict=True):
            item = items.get(row.question_content_id)
            # Archived releases remain usable for already frozen submissions;
            # archiving must never rewrite their immutable question bodies.
            if (
                item is None
                or item.status not in ("PUBLISHED", "ARCHIVED")
                or item.kind != "ASSESSMENT_QUESTION"
                or item.release_key != attempt.content_release
                or not valid_question(item)
                or item.body["skill"] != skill
                or len(item.body["prompt"]) > 16000
            ):
                raise InvalidEvidenceError(
                    "Pinned assessment question content is unavailable or invalid."
                )
            evidence.append(_question(db, row, item, user.id, now))
        if job.lease_expires_at <= db.scalar(select(func.clock_timestamp())):
            raise LostClaimError()
        return AssessmentEvidence(
            job_id=job.id,
            assessment_id=attempt.id,
            content_release=attempt.content_release,
            submitted_at=attempt.submitted_at,
            questions=tuple(evidence),
        )
