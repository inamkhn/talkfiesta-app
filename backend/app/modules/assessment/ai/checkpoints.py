"""Claim-fenced, per-response checkpoints for completed paid evaluation steps."""

import hashlib
import json
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import asdict
from typing import Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.infrastructure.database.sync_session import SyncSessionLocal
from app.modules.assessment.ai.evidence import AssessmentEvidence
from app.modules.assessment.models import AssessmentResponse
from app.modules.jobs.assessment_runner import (
    JobClaim,
    LostClaimError,
    RetryableEvaluationError,
    require_claim,
)


@contextmanager
def checkpoint_transaction():
    try:
        with SyncSessionLocal.begin() as db:
            yield db
    except OperationalError:
        raise RetryableEvaluationError(
            "Checkpoint storage temporarily unavailable."
        ) from None


class CheckpointStore:
    """Never keeps a transaction open during the supplied provider operation."""

    def __init__(self, claim: JobClaim, snapshot: AssessmentEvidence):
        if claim.job_id != snapshot.job_id:
            raise ValueError("Checkpoint job does not match evidence.")
        self.claim = claim
        self.snapshot = snapshot

    def _response(self, db, question):
        user, attempt, job, _ = require_claim(db, self.claim)
        if not user.is_active or attempt.id != self.snapshot.assessment_id:
            raise LostClaimError()
        row = db.scalar(
            select(AssessmentResponse)
            .where(
                AssessmentResponse.id == question.response_id,
                AssessmentResponse.assessment_attempt_id == attempt.id,
            )
            .with_for_update()
        )
        if (
            row is None
            or row.revision != question.revision
            or row.question_content_id != question.question_id
            or row.status not in ("ANSWERED", "SKIPPED")
        ):
            raise ValueError("Checkpoint response no longer matches frozen evidence.")
        if job.lease_expires_at <= db.scalar(select(func.clock_timestamp())):
            raise LostClaimError()
        return row

    def run[Output: BaseModel](
        self,
        *,
        skill: Literal["WRITING", "SPEAKING"],
        step: Literal["transcription", "language"],
        schema: type[Output],
        model: str,
        version: str,
        inputs: str,
        compute: Callable[[], Output],
    ) -> Output:
        if skill == "WRITING" and step != "language":
            raise ValueError("Unsupported checkpoint step.")
        question = next(q for q in self.snapshot.questions if q.skill == skill)
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "format": 1,
                    "job": str(self.claim.job_id),
                    "release": self.snapshot.content_release,
                    "evidence": asdict(question),
                    "model": model,
                    "version": version,
                    "inputs": inputs,
                    "rubric_version": settings.assessment_rubric_version,
                    "schema": schema.model_json_schema(),
                },
                sort_keys=True,
                default=str,
                ensure_ascii=False,
                allow_nan=False,
            ).encode()
        ).hexdigest()
        with checkpoint_transaction() as db:
            row = self._response(db, question)
            grading = row.grading if isinstance(row.grading, dict) else {}
            entries = grading.get("ai_checkpoints", {})
            cached = entries.get(step) if isinstance(entries, dict) else None
            if question.audio is not None and question.audio.delete_after <= db.scalar(
                select(func.clock_timestamp())
            ):
                cached = None
            if isinstance(cached, dict) and cached.get("fingerprint") == fingerprint:
                try:
                    return schema.model_validate(cached.get("output"))
                except ValidationError:
                    # Corrupted/old outputs cannot bypass current validation.
                    pass

        output = compute()
        output = schema.model_validate(output.model_dump())
        with checkpoint_transaction() as db:
            row = self._response(db, question)
            grading = dict(row.grading or {})
            previous = grading.get("ai_checkpoints", {})
            entries = dict(previous) if isinstance(previous, dict) else {}
            entries[step] = {
                "fingerprint": fingerprint,
                "output": output.model_dump(mode="json"),
            }
            grading["ai_checkpoints"] = entries
            row.grading = grading
        return output
