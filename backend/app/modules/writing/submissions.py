"""Create, resume, autosave, submit, and revise writing submissions."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from datetime import UTC, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
    ValidationAppError,
)
from app.modules.auth.models import User
from app.modules.content.models import ContentItem
from app.modules.jobs.models import AiJob, OutboxEvent
from app.modules.learning.models import ActivityCompletion, LearningPlan, ModuleProgress
from app.modules.practice.models import PracticeSubmission
from app.modules.writing.schemas import (
    CreateWritingRevisionRequest,
    SaveWritingDraftRequest,
    SaveWritingDraftResponse,
    SubmitWritingSubmissionRequest,
    SubmitWritingSubmissionResponse,
    WritingDraftResponse,
    WritingFeedbackReport,
    WritingJobState,
    WritingPortfolioItem,
    WritingPortfolioResponse,
    WritingPortfolioSort,
    WritingPrompt,
    WritingRevisionComparison,
    WritingRevisionsResponse,
    WritingRevisionVersionSummary,
    WritingSubmissionDetailResponse,
)
from app.modules.writing.service import WritingQueryService

_HTML_TAG_PATTERN = re.compile(r"<[A-Za-z!/][^>]*>")


def count_words(text: str) -> int:
    """Count whitespace-delimited words in plain text."""
    return len(text.split())


def sanitize_plain_text(raw_text: str) -> str:
    """Normalize line breaks and reject unsupported HTML markup or null bytes."""
    if "\x00" in raw_text or _HTML_TAG_PATTERN.search(raw_text):
        raise ValidationAppError(
            "Unsupported HTML or control characters in writing draft. Submit plain text only.",
            code="UNSUPPORTED_CONTENT",
        )
    return raw_text.replace("\r\n", "\n").replace("\r", "\n")


def extract_draft_text(raw_input: object) -> str:
    if isinstance(raw_input, dict):
        val = raw_input.get("text")
        if isinstance(val, str):
            return val
    return ""


def _project_prompt_from_item(item: ContentItem) -> WritingPrompt:
    body = item.body if isinstance(item.body, dict) else {}
    return WritingPrompt(
        id=item.id,
        kind=item.kind,
        title=item.title,
        writing_type=body.get("writing_type"),
        instructions=body.get("instructions"),
        target_word_count=body.get("target_word_count"),
        minimum_word_count=body.get("minimum_word_count"),
        maximum_word_count=body.get("maximum_word_count"),
        time_limit_minutes=body.get("time_limit_minutes"),
        tips=body.get("tips"),
    )


class WritingSubmissionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_or_resume(
        self, user_id: UUID, content_item_id: UUID, idempotency_key: str
    ) -> tuple[WritingDraftResponse, bool]:
        try:
            result = await self._create_or_resume(
                user_id, content_item_id, idempotency_key
            )
            await self.session.commit()
            return result
        except Exception:
            await self.session.rollback()
            raise

    async def _create_or_resume(
        self, user_id: UUID, content_item_id: UUID, idempotency_key: str
    ) -> tuple[WritingDraftResponse, bool]:
        user = await self.session.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if user is None:
            raise UnauthorizedError("The account no longer exists.")
        if not user.is_active:
            raise ForbiddenError("This account is inactive.")

        key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()

        # Standard lock order: user -> (plan, progress) -> content -> draft
        await self.session.execute(
            select(LearningPlan, ModuleProgress)
            .join(ModuleProgress, ModuleProgress.learning_plan_id == LearningPlan.id)
            .where(
                LearningPlan.user_id == user_id,
                LearningPlan.status == "ACTIVE",
                ModuleProgress.module == "WRITING",
            )
            .with_for_update(of=(LearningPlan, ModuleProgress))
            .execution_options(populate_existing=True)
        )

        # Reject idempotency key reuse across different content items.
        other_inputs = await self.session.scalars(
            select(PracticeSubmission.input).where(
                PracticeSubmission.user_id == user_id,
                PracticeSubmission.mode == "WRITING",
                PracticeSubmission.revision_number == 1,
                PracticeSubmission.content_item_id != content_item_id,
            )
        )
        for inp in other_inputs:
            if not isinstance(inp, dict):
                continue
            saved_hashes = inp.get("create_key_hashes") or []
            if key_hash in saved_hashes:
                raise ConflictError(
                    "This key was used with a different request.",
                    code="IDEMPOTENCY_KEY_REUSED",
                )

        today = await WritingQueryService(self.session).get_today(user_id)
        if today.prompt is None or today.module_status == "COMPLETED":
            raise ConflictError(
                "Writing is already completed.",
                code="ACTIVITY_ALREADY_COMPLETED",
            )

        credited = await self.session.scalar(
            select(ActivityCompletion.id).where(
                ActivityCompletion.user_id == user_id,
                ActivityCompletion.module_progress_id == today.module_progress_id,
                ActivityCompletion.content_item_id == content_item_id,
            )
        )
        if credited is not None:
            raise ConflictError(
                "This writing activity has already been completed.",
                code="ACTIVITY_ALREADY_COMPLETED",
            )

        if content_item_id != today.prompt.id:
            raise ConflictError(
                "Choose the currently assigned writing prompt.",
                code="ACTIVITY_NOT_CURRENT",
            )

        prompt_item = await self.session.scalar(
            select(ContentItem)
            .where(
                ContentItem.id == content_item_id,
                ContentItem.module == "WRITING",
                ContentItem.kind == "WRITING_LESSON",
                ContentItem.status == "PUBLISHED",
            )
            .with_for_update(read=True)
        )
        if prompt_item is None:
            raise ConflictError(
                "The required writing curriculum content is not available.",
                code="CURRICULUM_CONTENT_UNAVAILABLE",
            )

        draft = await self.session.scalar(
            select(PracticeSubmission)
            .where(
                PracticeSubmission.user_id == user_id,
                PracticeSubmission.module_progress_id == today.module_progress_id,
                PracticeSubmission.content_item_id == content_item_id,
                PracticeSubmission.mode == "WRITING",
                PracticeSubmission.status == "DRAFT",
                PracticeSubmission.revision_number == 1,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        created = draft is None
        if draft is None:
            revision_group_id = uuid4()
            draft = PracticeSubmission(
                id=uuid4(),
                user_id=user_id,
                module_progress_id=today.module_progress_id,
                content_item_id=content_item_id,
                mode="WRITING",
                status="DRAFT",
                evaluation_status="NOT_REQUIRED",
                edit_version=0,
                revision_group_id=revision_group_id,
                revision_number=1,
                input={
                    "text": "",
                    "create_key_hashes": [key_hash],
                },
            )
            self.session.add(draft)
            await self.session.flush()
        else:
            if draft.revision_group_id is None:
                draft.revision_group_id = uuid4()
            current_input = draft.input if isinstance(draft.input, dict) else {}
            hashes = list(current_input.get("create_key_hashes") or [])
            if key_hash not in hashes:
                hashes.append(key_hash)
                draft.input = {**current_input, "create_key_hashes": hashes}

        text = extract_draft_text(draft.input)
        return (
            WritingDraftResponse(
                id=draft.id,
                revision_group_id=draft.revision_group_id,
                revision_number=draft.revision_number,
                status="DRAFT",
                edit_version=draft.edit_version,
                text=text,
                word_count=count_words(text),
            ),
            created,
        )

    async def save_draft(
        self,
        user_id: UUID,
        submission_id: UUID,
        payload: SaveWritingDraftRequest,
    ) -> SaveWritingDraftResponse:
        try:
            result = await self._save_draft(user_id, submission_id, payload)
            await self.session.commit()
            return result
        except Exception:
            await self.session.rollback()
            raise

    async def _save_draft(
        self,
        user_id: UUID,
        submission_id: UUID,
        payload: SaveWritingDraftRequest,
    ) -> SaveWritingDraftResponse:
        user = await self.session.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if user is None:
            raise UnauthorizedError("The account no longer exists.")
        if not user.is_active:
            raise ForbiddenError("This account is inactive.")

        normalized_text = sanitize_plain_text(payload.text)

        draft = await self.session.scalar(
            select(PracticeSubmission)
            .where(
                PracticeSubmission.id == submission_id,
                PracticeSubmission.user_id == user_id,
                PracticeSubmission.mode == "WRITING",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if draft is None:
            raise NotFoundError("Writing submission not found.")
        if draft.status != "DRAFT":
            raise ConflictError(
                "Submitted writing versions are immutable and cannot be edited.",
                code="PRACTICE_NOT_EDITABLE",
            )

        existing_text = extract_draft_text(draft.input)
        current_input = draft.input if isinstance(draft.input, dict) else {}
        now = datetime.now(UTC)

        if payload.expected_edit_version != draft.edit_version:
            if (
                payload.expected_edit_version == draft.edit_version - 1
                and existing_text == normalized_text
            ):
                saved_at_raw = current_input.get("saved_at")
                saved_at = (
                    datetime.fromisoformat(saved_at_raw)
                    if isinstance(saved_at_raw, str)
                    else now
                )
                return SaveWritingDraftResponse(
                    id=draft.id,
                    status="DRAFT",
                    edit_version=draft.edit_version,
                    word_count=count_words(existing_text),
                    saved_at=saved_at,
                )
            raise ConflictError(
                "The writing draft has changed. Reload its current version.",
                code="STALE_EDIT_VERSION",
            )

        draft.input = {
            **current_input,
            "text": normalized_text,
            "saved_at": now.isoformat(),
        }
        draft.edit_version += 1
        return SaveWritingDraftResponse(
            id=draft.id,
            status="DRAFT",
            edit_version=draft.edit_version,
            word_count=count_words(normalized_text),
            saved_at=now,
        )

    async def submit(
        self,
        user_id: UUID,
        submission_id: UUID,
        idempotency_key: str,
        payload: SubmitWritingSubmissionRequest | None = None,
    ) -> SubmitWritingSubmissionResponse:
        try:
            result = await self._submit(
                user_id, submission_id, idempotency_key, payload
            )
            await self.session.commit()
            return result
        except Exception:
            await self.session.rollback()
            raise

    async def _submit(
        self,
        user_id: UUID,
        submission_id: UUID,
        idempotency_key: str,
        payload: SubmitWritingSubmissionRequest | None = None,
    ) -> SubmitWritingSubmissionResponse:
        user = await self.session.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if user is None:
            raise UnauthorizedError("The account no longer exists.")
        if not user.is_active:
            raise ForbiddenError("This account is inactive.")

        key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()

        # Reject idempotency key reuse across different writing submissions.
        other_feedbacks = await self.session.scalars(
            select(PracticeSubmission.feedback).where(
                PracticeSubmission.user_id == user_id,
                PracticeSubmission.mode == "WRITING",
                PracticeSubmission.id != submission_id,
            )
        )
        for fb in other_feedbacks:
            if not isinstance(fb, dict):
                continue
            if key_hash in (fb.get("submit_key_hashes") or []):
                raise ConflictError(
                    "This key was used for a different writing submission.",
                    code="IDEMPOTENCY_KEY_REUSED",
                )

        # Standard lock order: user -> (plan, progress) -> content -> draft
        await self.session.execute(
            select(LearningPlan, ModuleProgress)
            .join(ModuleProgress, ModuleProgress.learning_plan_id == LearningPlan.id)
            .where(
                LearningPlan.user_id == user_id,
                LearningPlan.status == "ACTIVE",
                ModuleProgress.module == "WRITING",
            )
            .with_for_update(of=(LearningPlan, ModuleProgress))
            .execution_options(populate_existing=True)
        )

        draft = await self.session.scalar(
            select(PracticeSubmission)
            .where(
                PracticeSubmission.id == submission_id,
                PracticeSubmission.user_id == user_id,
                PracticeSubmission.mode == "WRITING",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if draft is None:
            raise NotFoundError("Writing submission not found.")

        if draft.status == "ACCEPTED":
            fb = draft.feedback if isinstance(draft.feedback, dict) else {}
            receipt = fb.get("submit_response")
            if not isinstance(receipt, dict):
                raise ConflictError(
                    "The saved writing submission receipt is missing.",
                    code="WRITING_STATE_INCONSISTENT",
                )
            hashes = list(fb.get("submit_key_hashes") or [])
            if key_hash not in hashes:
                hashes.append(key_hash)
                draft.feedback = {**fb, "submit_key_hashes": hashes}
            return SubmitWritingSubmissionResponse.model_validate(receipt)

        if draft.status != "DRAFT":
            raise ConflictError(
                "This writing submission cannot be submitted in its current state.",
                code="PRACTICE_NOT_SUBMITTABLE",
            )

        progress = (
            await self.session.get(ModuleProgress, draft.module_progress_id)
            if draft.module_progress_id is not None
            else None
        )
        plan = (
            await self.session.get(LearningPlan, progress.learning_plan_id)
            if progress is not None
            else None
        )

        if draft.revision_number == 1:
            if progress is None or progress.status != "ACTIVE":
                raise ConflictError(
                    "Writing enrollment is not active.",
                    code="PRACTICE_NOT_SUBMITTABLE",
                )
            if plan is None or plan.status != "ACTIVE":
                raise ConflictError(
                    "Active learning plan not found.",
                    code="PRACTICE_NOT_SUBMITTABLE",
                )

            prompt_item = await self.session.scalar(
                select(ContentItem)
                .where(
                    ContentItem.id == draft.content_item_id,
                    ContentItem.release_key == progress.content_release,
                    ContentItem.module == "WRITING",
                    ContentItem.kind == "WRITING_LESSON",
                    ContentItem.slot == "CORE",
                    ContentItem.cycle == plan.cycle,
                    ContentItem.day == progress.current_day,
                    ContentItem.cefr_level == progress.cefr_level,
                    ContentItem.goal_variant == progress.goal_variant,
                    ContentItem.status == "PUBLISHED",
                )
                .with_for_update(read=True)
            )
            if prompt_item is None:
                raise ConflictError(
                    "This draft does not match the currently assigned writing prompt.",
                    code="ACTIVITY_NOT_CURRENT",
                )

            credited_days = set(
                await self.session.scalars(
                    select(ContentItem.day)
                    .join(
                        ActivityCompletion,
                        ActivityCompletion.content_item_id == ContentItem.id,
                    )
                    .where(
                        ActivityCompletion.user_id == user_id,
                        ActivityCompletion.module_progress_id == progress.id,
                        ContentItem.release_key == progress.content_release,
                        ContentItem.module == "WRITING",
                        ContentItem.kind == "WRITING_LESSON",
                        ContentItem.slot == "CORE",
                        ContentItem.cycle == plan.cycle,
                        ContentItem.cefr_level == progress.cefr_level,
                        ContentItem.goal_variant == progress.goal_variant,
                        ContentItem.status.in_(("PUBLISHED", "ARCHIVED")),
                    )
                )
            )
            if credited_days != set(range(1, progress.current_day)):
                raise ConflictError(
                    "Writing progress and completion credits disagree.",
                    code="WRITING_STATE_INCONSISTENT",
                )
        else:
            prompt_item = await self.session.scalar(
                select(ContentItem)
                .where(
                    ContentItem.id == draft.content_item_id,
                    ContentItem.module == "WRITING",
                    ContentItem.kind == "WRITING_LESSON",
                    ContentItem.status.in_(("PUBLISHED", "ARCHIVED")),
                )
                .with_for_update(read=True)
            )
            if prompt_item is None:
                raise ConflictError(
                    "The writing prompt content for this revision is unavailable.",
                    code="CURRICULUM_CONTENT_UNAVAILABLE",
                )

        try:
            prompt = _project_prompt_from_item(prompt_item)
        except ValidationError:
            raise ServiceUnavailableError(
                "The saved writing lesson is incomplete. Please try again later.",
                code="WRITING_LESSON_UNAVAILABLE",
            ) from None

        current_input = draft.input if isinstance(draft.input, dict) else {}
        if payload is not None and payload.text is not None:
            raw_text = payload.text
        else:
            raw_text = extract_draft_text(current_input)

        text = sanitize_plain_text(raw_text).strip()
        word_count = count_words(text)
        if (
            word_count < prompt.minimum_word_count
            or word_count > prompt.maximum_word_count
        ):
            raise ValidationAppError(
                f"Writing submission must be between {prompt.minimum_word_count} and {prompt.maximum_word_count} words (received {word_count}).",
                code="WORD_COUNT_OUT_OF_RANGE",
            )

        now = datetime.now(UTC)
        if draft.revision_group_id is None:
            draft.revision_group_id = uuid4()

        draft.input = {
            **current_input,
            "text": text,
            "word_count": word_count,
        }
        draft.status = "ACCEPTED"
        draft.evaluation_status = "PENDING"
        draft.submitted_at = now

        next_day: int | None = None
        if draft.revision_number == 1 and progress is not None:
            self.session.add(
                ActivityCompletion(
                    user_id=user_id,
                    module_progress_id=progress.id,
                    content_item_id=prompt_item.id,
                    source_submission_id=draft.id,
                    local_practice_date=now.astimezone(ZoneInfo(user.timezone)).date(),
                    completed_at=now,
                )
            )
            day = progress.current_day
            if day == 21:
                progress.status = "COMPLETED"
                progress.completed_at = now
                next_day = None
            else:
                progress.current_day = day + 1
                next_day = day + 1
            progress.updated_at = now
        elif progress is not None and progress.status == "ACTIVE":
            next_day = progress.current_day

        job = AiJob(
            id=uuid4(),
            user_id=user_id,
            job_type="WRITING_FEEDBACK",
            practice_submission_id=draft.id,
            status="PENDING",
            idempotency_key=f"writing:{draft.id}:feedback:v1",
        )
        self.session.add(job)
        await self.session.flush()

        self.session.add(
            OutboxEvent(
                ai_job_id=job.id,
                event_type="WRITING_FEEDBACK_REQUESTED",
                payload={
                    "job_id": str(job.id),
                    "practice_submission_id": str(draft.id),
                },
            )
        )

        response = SubmitWritingSubmissionResponse(
            id=draft.id,
            revision_group_id=draft.revision_group_id,
            revision_number=draft.revision_number,
            activity_status="COMPLETED",
            evaluation_status="PENDING",
            job_id=job.id,
            feedback_url=f"/api/v1/writing/submissions/{draft.id}",
            next_module_day=next_day,
        )
        draft.feedback = {
            "submit_response": response.model_dump(mode="json"),
            "submit_key_hashes": [key_hash],
        }
        return response

    async def get_submission(
        self, user_id: UUID, submission_id: UUID
    ) -> WritingSubmissionDetailResponse:
        submission = await self.session.scalar(
            select(PracticeSubmission).where(
                PracticeSubmission.id == submission_id,
                PracticeSubmission.user_id == user_id,
                PracticeSubmission.mode == "WRITING",
            )
        )
        if submission is None:
            raise NotFoundError("Writing submission not found.")

        job_row = await self.session.scalar(
            select(AiJob)
            .where(
                AiJob.practice_submission_id == submission.id,
                AiJob.user_id == user_id,
                AiJob.job_type == "WRITING_FEEDBACK",
            )
            .order_by(AiJob.created_at.desc(), AiJob.id.desc())
            .limit(1)
        )

        text = extract_draft_text(submission.input)
        word_count = count_words(text)
        job_state = _build_job_state(submission, job_row)
        feedback = extract_feedback_report(submission, job_row)

        return WritingSubmissionDetailResponse(
            id=submission.id,
            revision_group_id=submission.revision_group_id,
            revision_number=submission.revision_number,
            status=submission.status,
            evaluation_status=submission.evaluation_status,
            content_item_id=submission.content_item_id,
            edit_version=submission.edit_version,
            submitted_text=text,
            word_count=word_count,
            feedback=feedback,
            job=job_state,
        )

    async def create_revision(
        self,
        user_id: UUID,
        submission_id: UUID,
        idempotency_key: str,
        payload: CreateWritingRevisionRequest | None = None,
    ) -> tuple[WritingDraftResponse, bool]:
        try:
            result = await self._create_revision(
                user_id, submission_id, idempotency_key, payload
            )
            await self.session.commit()
            return result
        except Exception:
            await self.session.rollback()
            raise

    async def _create_revision(
        self,
        user_id: UUID,
        submission_id: UUID,
        idempotency_key: str,
        payload: CreateWritingRevisionRequest | None = None,
    ) -> tuple[WritingDraftResponse, bool]:
        user = await self.session.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if user is None:
            raise UnauthorizedError("The account no longer exists.")
        if not user.is_active:
            raise ForbiddenError("This account is inactive.")

        key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()

        anchor = await self.session.scalar(
            select(PracticeSubmission)
            .where(
                PracticeSubmission.id == submission_id,
                PracticeSubmission.user_id == user_id,
                PracticeSubmission.mode == "WRITING",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if anchor is None:
            raise NotFoundError("Writing submission not found.")

        if anchor.revision_group_id is None:
            anchor.revision_group_id = uuid4()
            await self.session.flush()

        group_id = anchor.revision_group_id

        # Reject idempotency key reuse across different revision groups.
        other_revisions = await self.session.scalars(
            select(PracticeSubmission).where(
                PracticeSubmission.user_id == user_id,
                PracticeSubmission.mode == "WRITING",
                PracticeSubmission.revision_number > 1,
                PracticeSubmission.revision_group_id != group_id,
            )
        )
        for other in other_revisions:
            inp = other.input if isinstance(other.input, dict) else {}
            if key_hash in (inp.get("create_key_hashes") or []):
                raise ConflictError(
                    "This key was used with a different revision request.",
                    code="IDEMPOTENCY_KEY_REUSED",
                )

        group_rows = list(
            await self.session.scalars(
                select(PracticeSubmission)
                .where(
                    PracticeSubmission.user_id == user_id,
                    PracticeSubmission.mode == "WRITING",
                    PracticeSubmission.revision_group_id == group_id,
                )
                .order_by(PracticeSubmission.revision_number.asc())
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        if not group_rows:
            raise NotFoundError("Writing submission not found.")

        requested_base_id = (
            payload.base_submission_id if payload is not None else None
        )
        latest = group_rows[-1]

        # Reuse an existing unsubmitted revision draft (revision_number > 1) if present.
        if latest.status == "DRAFT" and latest.revision_number > 1:
            base_row = group_rows[-2] if len(group_rows) >= 2 else anchor
            if requested_base_id is not None and requested_base_id not in (
                base_row.id,
                anchor.id,
            ):
                raise ConflictError(
                    "Base submission does not match the active revision draft.",
                    code="STALE_BASE_SUBMISSION",
                )
            current_input = latest.input if isinstance(latest.input, dict) else {}
            hashes = list(current_input.get("create_key_hashes") or [])
            if key_hash not in hashes:
                hashes.append(key_hash)
                latest.input = {**current_input, "create_key_hashes": hashes}
            text = extract_draft_text(latest.input)
            return (
                WritingDraftResponse(
                    id=latest.id,
                    revision_group_id=group_id,
                    revision_number=latest.revision_number,
                    status="DRAFT",
                    edit_version=latest.edit_version,
                    text=text,
                    word_count=count_words(text),
                ),
                False,
            )

        if requested_base_id is not None and requested_base_id != latest.id:
            raise ConflictError(
                "Revisions must be created from the latest evaluated version.",
                code="STALE_BASE_SUBMISSION",
            )

        if (
            latest.status != "ACCEPTED"
            or latest.evaluation_status != "COMPLETED"
        ):
            raise ConflictError(
                "A revision can only be started after the previous version has completed evaluation.",
                code="EVALUATION_NOT_COMPLETED",
            )

        if latest.revision_number >= 4:
            raise ConflictError(
                "Maximum of 3 revisions (4 total versions) reached for this writing prompt.",
                code="REVISION_LIMIT_REACHED",
            )

        next_revision_number = latest.revision_number + 1
        initial_text = extract_draft_text(latest.input)

        draft = PracticeSubmission(
            id=uuid4(),
            user_id=user_id,
            module_progress_id=latest.module_progress_id,
            content_item_id=latest.content_item_id,
            mode="WRITING",
            status="DRAFT",
            evaluation_status="NOT_REQUIRED",
            edit_version=0,
            revision_group_id=group_id,
            revision_number=next_revision_number,
            input={
                "text": initial_text,
                "base_submission_id": str(latest.id),
                "create_key_hashes": [key_hash],
            },
        )
        self.session.add(draft)
        await self.session.flush()

        return (
            WritingDraftResponse(
                id=draft.id,
                revision_group_id=group_id,
                revision_number=draft.revision_number,
                status="DRAFT",
                edit_version=draft.edit_version,
                text=initial_text,
                word_count=count_words(initial_text),
            ),
            True,
        )

    async def get_revisions(
        self, user_id: UUID, submission_id: UUID
    ) -> WritingRevisionsResponse:
        anchor = await self.session.scalar(
            select(PracticeSubmission).where(
                PracticeSubmission.id == submission_id,
                PracticeSubmission.user_id == user_id,
                PracticeSubmission.mode == "WRITING",
            )
        )
        if anchor is None:
            raise NotFoundError("Writing submission not found.")

        group_id = anchor.revision_group_id or anchor.id
        if anchor.revision_group_id is not None:
            group_rows = list(
                await self.session.scalars(
                    select(PracticeSubmission)
                    .where(
                        PracticeSubmission.user_id == user_id,
                        PracticeSubmission.mode == "WRITING",
                        PracticeSubmission.revision_group_id == group_id,
                    )
                    .order_by(PracticeSubmission.revision_number.asc())
                )
            )
        else:
            group_rows = [anchor]

        versions = [
            WritingRevisionVersionSummary(
                id=row.id,
                version=row.revision_number,
                status=row.status,
                evaluation_status=row.evaluation_status,
                overall_score=_extract_overall_score(row),
            )
            for row in group_rows
        ]

        latest_comparison: WritingRevisionComparison | None = None
        for row in reversed(group_rows):
            if row.revision_number > 1 and row.evaluation_status == "COMPLETED":
                comp = _extract_revision_comparison(row)
                if comp is not None:
                    latest_comparison = comp
                    break

        return WritingRevisionsResponse(
            revision_group_id=group_id,
            max_revisions=3,
            versions=versions,
            latest_comparison=latest_comparison,
        )

    async def get_portfolio(
        self,
        user_id: UUID,
        *,
        limit: int = 20,
        cursor: str | None = None,
        sort: WritingPortfolioSort = "recent",
    ) -> WritingPortfolioResponse:
        _ = sort
        cursor_point = _decode_portfolio_cursor(cursor) if cursor else None

        stmt = (
            select(PracticeSubmission, ContentItem.title)
            .join(ContentItem, ContentItem.id == PracticeSubmission.content_item_id)
            .where(
                PracticeSubmission.user_id == user_id,
                PracticeSubmission.mode == "WRITING",
                PracticeSubmission.revision_number == 1,
                PracticeSubmission.status == "ACCEPTED",
                PracticeSubmission.submitted_at.is_not(None),
                PracticeSubmission.revision_group_id.is_not(None),
            )
        )
        if cursor_point is not None:
            cursor_dt, cursor_group_id = cursor_point
            stmt = stmt.where(
                or_(
                    PracticeSubmission.submitted_at < cursor_dt,
                    and_(
                        PracticeSubmission.submitted_at == cursor_dt,
                        PracticeSubmission.revision_group_id < cursor_group_id,
                    ),
                )
            )
        stmt = stmt.order_by(
            PracticeSubmission.submitted_at.desc(),
            PracticeSubmission.revision_group_id.desc(),
        ).limit(limit + 1)

        rows = (await self.session.execute(stmt)).all()
        has_next = len(rows) > limit
        page_rows = rows[:limit]

        group_ids = [
            row[0].revision_group_id
            for row in page_rows
            if row[0].revision_group_id is not None
        ]
        versions_by_group: dict[UUID, list[PracticeSubmission]] = {}
        if group_ids:
            all_versions = await self.session.scalars(
                select(PracticeSubmission)
                .where(
                    PracticeSubmission.user_id == user_id,
                    PracticeSubmission.mode == "WRITING",
                    PracticeSubmission.status == "ACCEPTED",
                    PracticeSubmission.revision_group_id.in_(group_ids),
                )
                .order_by(PracticeSubmission.revision_number.asc())
            )
            for v in all_versions:
                if v.revision_group_id is not None:
                    versions_by_group.setdefault(v.revision_group_id, []).append(v)

        items: list[WritingPortfolioItem] = []
        for original_sub, title in page_rows:
            group_id = original_sub.revision_group_id
            if group_id is None or original_sub.submitted_at is None:
                continue
            group_versions = versions_by_group.get(group_id) or [original_sub]
            latest = group_versions[-1]
            submitted_at = (
                original_sub.submitted_at
                if original_sub.submitted_at.tzinfo is not None
                else original_sub.submitted_at.replace(tzinfo=UTC)
            )
            items.append(
                WritingPortfolioItem(
                    revision_group_id=group_id,
                    title=title,
                    content_item_id=original_sub.content_item_id,
                    original_submitted_at=submitted_at,
                    latest_version=latest.revision_number,
                    latest_evaluation_status=latest.evaluation_status,
                    latest_score=_extract_overall_score(latest),
                )
            )

        next_cursor: str | None = None
        if has_next and page_rows:
            last_sub = page_rows[-1][0]
            if (
                last_sub.submitted_at is not None
                and last_sub.revision_group_id is not None
            ):
                last_dt = (
                    last_sub.submitted_at
                    if last_sub.submitted_at.tzinfo is not None
                    else last_sub.submitted_at.replace(tzinfo=UTC)
                )
                next_cursor = _encode_portfolio_cursor(
                    last_dt, last_sub.revision_group_id
                )

        return WritingPortfolioResponse(items=items, next_cursor=next_cursor)





def _build_job_state(
    submission: PracticeSubmission, job_row: AiJob | None
) -> WritingJobState | None:
    if submission.status == "DRAFT":
        return None
    if job_row is not None:
        status = job_row.status
        if status == "PENDING":
            return WritingJobState(
                status="PENDING",
                stage=job_row.stage or "QUEUED",
                retry_after_seconds=3,
            )
        if status == "RETRYABLE":
            return WritingJobState(
                status="RETRYABLE",
                stage=job_row.stage or "RETRY_SCHEDULED",
                retry_after_seconds=5,
            )
        if status == "RUNNING":
            return WritingJobState(
                status="RUNNING",
                stage=job_row.stage or "EVALUATING_WRITING",
                retry_after_seconds=3,
            )
        if status == "SUCCEEDED":
            return WritingJobState(
                status="SUCCEEDED",
                stage=job_row.stage or "DONE",
            )
        if status == "FAILED":
            return WritingJobState(
                status="FAILED",
                stage=job_row.stage or "FAILED",
                error_message="Automated writing feedback could not be generated right now. Your completion credit is saved.",
            )

    eval_status = submission.evaluation_status
    if eval_status == "COMPLETED":
        return WritingJobState(status="SUCCEEDED", stage="DONE")
    if eval_status == "PROCESSING":
        return WritingJobState(
            status="RUNNING", stage="EVALUATING_WRITING", retry_after_seconds=3
        )
    if eval_status == "PENDING":
        return WritingJobState(
            status="PENDING", stage="QUEUED", retry_after_seconds=3
        )
    if eval_status == "FAILED":
        return WritingJobState(
            status="FAILED",
            stage="FAILED",
            error_message="Automated writing feedback could not be generated right now. Your completion credit is saved.",
        )
    return None


def extract_feedback_report(
    submission: PracticeSubmission, job_row: AiJob | None
) -> WritingFeedbackReport | None:
    if submission.evaluation_status != "COMPLETED":
        return None
    raw_fb = submission.feedback if isinstance(submission.feedback, dict) else {}
    report_dict = raw_fb.get("report") if isinstance(raw_fb.get("report"), dict) else raw_fb
    if not isinstance(report_dict, dict) or "scores" not in report_dict:
        return None
    payload = dict(report_dict)
    if "rubric_version" not in payload:
        payload["rubric_version"] = (
            job_row.rubric_version
            if job_row is not None and job_row.rubric_version
            else "writing-rubric-v1"
        )
    allowed_keys = {
        "rubric_version",
        "scores",
        "corrections",
        "strengths",
        "improvements",
        "revised_example",
        "revision_comparison",
    }
    filtered = {k: v for k, v in payload.items() if k in allowed_keys}
    try:
        return WritingFeedbackReport.model_validate(filtered)
    except ValidationError:
        raise ServiceUnavailableError(
            "The saved writing evaluation feedback is incomplete. Please try again later.",
            code="WRITING_FEEDBACK_UNAVAILABLE",
        ) from None


def _extract_overall_score(row: PracticeSubmission) -> int | None:
    if row.evaluation_status != "COMPLETED":
        return None
    if row.score is not None:
        return max(0, min(100, round(float(row.score))))
    raw_fb = row.feedback if isinstance(row.feedback, dict) else {}
    report = raw_fb.get("report") if isinstance(raw_fb.get("report"), dict) else raw_fb
    if isinstance(report, dict):
        scores = report.get("scores")
        if isinstance(scores, dict) and isinstance(scores.get("overall"), int | float):
            return max(0, min(100, round(float(scores["overall"]))))
    return None


def _extract_revision_comparison(
    row: PracticeSubmission,
) -> WritingRevisionComparison | None:
    raw_fb = row.feedback if isinstance(row.feedback, dict) else {}
    comp_raw = raw_fb.get("revision_comparison")
    if not isinstance(comp_raw, dict):
        report = raw_fb.get("report")
        if isinstance(report, dict):
            comp_raw = report.get("revision_comparison")
    if not isinstance(comp_raw, dict):
        return None
    try:
        return WritingRevisionComparison.model_validate(comp_raw)
    except ValidationError:
        return None


def _encode_portfolio_cursor(submitted_at: datetime, group_id: UUID) -> str:
    payload = json.dumps(
        {"t": submitted_at.astimezone(UTC).isoformat(), "g": str(group_id)},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_portfolio_cursor(cursor: str) -> tuple[datetime, UUID]:
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        if not isinstance(raw, dict):
            raise TypeError("Cursor payload must be an object.")
        dt = datetime.fromisoformat(str(raw["t"]))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        group_id = UUID(str(raw["g"]))
    except (binascii.Error, UnicodeDecodeError, ValueError, KeyError, TypeError):
        raise ValidationAppError(
            "Invalid pagination cursor.",
            code="INVALID_CURSOR",
        ) from None
    return dt, group_id





