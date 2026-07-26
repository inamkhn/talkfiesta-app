import uuid
import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api import deps
from app.crud import user as crud_user
from app.crud import writing as crud_writing
from app.db.models.user import User
from app.db.models.writing import WritingSubmission
from app.db.models.enums import SubmissionStatus
from app.middleware.rate_limit import check_ai_rate_limit, refund_ai_rate_limit
from app.schemas.writing import (
    WritingPromptResponse,
    DraftSaveRequest,
    DraftSaveResponse,
    SubmissionCreateRequest,
    SubmissionReviseRequest,
    WritingSubmissionResponse,
    WritingPortfolioResponse,
)
from app.workers.writing_tasks import process_writing_submission

logger = logging.getLogger("app.api.v1.writing")

router = APIRouter()


def _validate_content(content: str, label: str = "Content") -> None:
    """Shared length validation for submissions and revisions."""
    if len(content.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} must be at least 10 characters long.",
        )
    if len(content) > 10000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} is too long. Maximum allowed length is 10,000 characters.",
        )


@router.get("/prompt/{day}", response_model=WritingPromptResponse)
def get_daily_prompt(
    day: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve the writing prompt for the user's current cycle and requested day.
    """
    profile = crud_user.get_learning_profile(db, user_id=current_user.id)
    cycle = profile.current_cycle if profile else 1
    cefr_level = profile.target_cefr_level if profile else "A1"

    prompt = crud_writing.get_prompt_by_cycle_and_day(db, cycle=cycle, day=day, target_cefr_level=cefr_level)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No writing prompt found for this day with level {cefr_level}.",
        )
    return prompt


@router.post("/draft/save", response_model=DraftSaveResponse)
def save_writing_draft(
    draft_data: DraftSaveRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Lightweight, frequent auto-save endpoint to persist the user's text.
    Does not trigger AI grading. Content is written through to the database
    so drafts survive restarts and cache evictions.
    """
    prompt = crud_writing.get_prompt_by_id(db, prompt_id=draft_data.prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Writing prompt not found.",
        )

    try:
        submission, version = crud_writing.save_draft(
            db=db,
            user_id=current_user.id,
            prompt_id=draft_data.prompt_id,
            content=draft_data.content,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An evaluation is already in progress for this prompt.",
        )

    return DraftSaveResponse(
        submission_id=submission.id,
        status=submission.status,
        last_edited_at=version.created_at,
    )


@router.post("/submit", response_model=WritingSubmissionResponse)
def submit_writing(
    submission_data: SubmissionCreateRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Submit an essay for AI evaluation. Triggers the LangGraph pipeline asynchronously.
    """
    # Validate BEFORE consuming AI quota
    _validate_content(submission_data.content)

    # Verify prompt exists
    prompt = crud_writing.get_prompt_by_id(db, prompt_id=submission_data.prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Writing prompt not found.",
        )

    # Fast-path rejection of double submissions (race-safe enforcement is
    # handled by the unique partial index in crud.submit_writing_essay)
    existing_processing = db.query(WritingSubmission).filter(
        WritingSubmission.user_id == current_user.id,
        WritingSubmission.prompt_id == submission_data.prompt_id,
        WritingSubmission.status == SubmissionStatus.PROCESSING,
    ).first()
    if existing_processing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An evaluation is already in progress for this prompt.",
        )

    # All validations passed: consume AI quota
    check_ai_rate_limit(current_user)

    # Calculate actual word count server-side
    calculated_word_count = len(submission_data.content.strip().split())

    # Submit essay
    try:
        submission, version = crud_writing.submit_writing_essay(
            db=db,
            user_id=current_user.id,
            prompt_id=submission_data.prompt_id,
            content=submission_data.content,
            word_count=calculated_word_count,
            time_spent_seconds=submission_data.time_spent_seconds,
        )
    except ValueError as e:
        refund_ai_rate_limit(str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Trigger Celery task asynchronously and capture job ID. If the broker is
    # unavailable, revert the submission to a PENDING draft instead of leaving
    # it stuck in PROCESSING.
    try:
        task = process_writing_submission.delay(str(submission.id), str(version.id))
    except Exception as e:
        logger.error(f"Failed to dispatch writing evaluation task: {e}")
        submission.status = SubmissionStatus.PENDING
        db.commit()
        refund_ai_rate_limit(str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Evaluation service is temporarily unavailable. Your draft has been saved; please try again shortly.",
        )

    submission.processing_job_id = task.id
    db.commit()
    db.refresh(submission)

    return submission


@router.get("/submission/{id}", response_model=WritingSubmissionResponse)
def get_submission(
    id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve the status and results of a specific writing submission.
    """
    submission = crud_writing.get_submission_by_id(db, submission_id=id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found.",
        )

    # Ensure user can only access their own submissions
    if submission.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this submission.",
        )

    return submission


@router.post("/submission/{id}/revise", response_model=WritingSubmissionResponse)
def revise_submission(
    id: uuid.UUID,
    revision_data: SubmissionReviseRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Submit a revised version of an essay. Re-runs the evaluation pipeline.
    """
    submission = crud_writing.get_submission_by_id(db, submission_id=id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found.",
        )

    if submission.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to revise this submission.",
        )

    if submission.status == SubmissionStatus.PROCESSING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot revise a submission that is currently processing.",
        )

    # Validate BEFORE consuming AI quota
    _validate_content(revision_data.content, label="Revised content")

    prior_status = submission.status

    # All validations passed: consume AI quota
    check_ai_rate_limit(current_user)

    # Calculate actual word count server-side
    calculated_word_count = len(revision_data.content.strip().split())

    try:
        submission, version = crud_writing.create_revision(
            db=db,
            submission_id=id,
            content=revision_data.content,
            word_count=calculated_word_count,
            time_spent_seconds=revision_data.time_spent_seconds,
        )
    except ValueError as e:
        refund_ai_rate_limit(str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Dispatch the evaluation task; on broker failure, fully roll back the
    # revision (delete version, restore count/status) and refund quota.
    try:
        task = process_writing_submission.delay(str(submission.id), str(version.id))
    except Exception as e:
        logger.error(f"Failed to dispatch revision evaluation task: {e}")
        crud_writing.rollback_revision(
            db, submission_id=submission.id, version_id=version.id, prior_status=prior_status
        )
        refund_ai_rate_limit(str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Evaluation service is temporarily unavailable. Please try again shortly.",
        )

    submission.processing_job_id = task.id
    db.commit()
    db.refresh(submission)

    return submission


@router.get("/portfolio", response_model=WritingPortfolioResponse)
def get_portfolio(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Fetch completed/processing writing submissions for the authenticated user (paginated).
    """
    submissions = crud_writing.get_user_portfolio(db, user_id=current_user.id, limit=limit, offset=offset)
    return WritingPortfolioResponse(submissions=submissions)
