import uuid
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.crud import user as crud_user
from app.crud import writing as crud_writing
from app.db.models.user import User
from app.db.models.enums import SubmissionStatus
from app.middleware.rate_limit import check_ai_rate_limit
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

router = APIRouter()


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

    prompt = crud_writing.get_prompt_by_cycle_and_day(db, cycle=cycle, day=day)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No writing prompt found for this day.",
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
    Does not trigger AI grading.
    """
    submission, version = crud_writing.save_draft(
        db=db,
        user_id=current_user.id,
        prompt_id=draft_data.prompt_id,
        content=draft_data.content,
    )
    return DraftSaveResponse(
        submission_id=submission.id,
        status=submission.status,
        last_edited_at=version.created_at,
    )


@router.post(
    "/submit",
    response_model=WritingSubmissionResponse,
    dependencies=[Depends(check_ai_rate_limit)],
)
def submit_writing(
    submission_data: SubmissionCreateRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Submit an essay for AI evaluation. Triggers the LangGraph pipeline asynchronously.
    """
    # Verify prompt exists
    prompt = crud_writing.get_prompt_by_id(db, prompt_id=submission_data.prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Writing prompt not found.",
        )

    # Submit essay
    submission, version = crud_writing.submit_writing_essay(
        db=db,
        user_id=current_user.id,
        prompt_id=submission_data.prompt_id,
        content=submission_data.content,
        word_count=submission_data.word_count,
        time_spent_seconds=submission_data.time_spent_seconds,
    )

    # Trigger Celery task asynchronously
    process_writing_submission.delay(str(submission.id), str(version.id))

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


@router.post(
    "/submission/{id}/revise",
    response_model=WritingSubmissionResponse,
    dependencies=[Depends(check_ai_rate_limit)],
)
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

    try:
        submission, version = crud_writing.create_revision(
            db=db,
            submission_id=id,
            content=revision_data.content,
            word_count=revision_data.word_count,
            time_spent_seconds=revision_data.time_spent_seconds,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Trigger Celery task asynchronously for the new revision
    process_writing_submission.delay(str(submission.id), str(version.id))

    return submission


@router.get("/portfolio", response_model=WritingPortfolioResponse)
def get_portfolio(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Fetch all completed/processing writing submissions for the authenticated user.
    """
    submissions = crud_writing.get_user_portfolio(db, user_id=current_user.id)
    return WritingPortfolioResponse(submissions=submissions)
