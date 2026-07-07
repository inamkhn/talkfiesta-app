import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session, joinedload

from app.db.models.writing import WritingPrompt, WritingSubmission, WritingSubmissionVersion
from app.db.models.enums import SubmissionStatus


def get_prompt_by_cycle_and_day(db: Session, cycle: int, day: int) -> Optional[WritingPrompt]:
    """
    Retrieve a writing prompt for a specific cycle and day.
    """
    return (
        db.query(WritingPrompt)
        .filter(WritingPrompt.cycle == cycle, WritingPrompt.day == day)
        .first()
    )


def get_prompt_by_id(db: Session, prompt_id: uuid.UUID) -> Optional[WritingPrompt]:
    """
    Retrieve a specific writing prompt by its UUID.
    """
    return db.query(WritingPrompt).filter(WritingPrompt.id == prompt_id).first()


def get_submission_by_id(db: Session, submission_id: uuid.UUID) -> Optional[WritingSubmission]:
    """
    Retrieve a writing submission by its ID, with all its versions eagerly loaded.
    """
    return (
        db.query(WritingSubmission)
        .filter(WritingSubmission.id == submission_id)
        .options(joinedload(WritingSubmission.versions))
        .first()
    )


def get_pending_submission_by_prompt(
    db: Session, user_id: uuid.UUID, prompt_id: uuid.UUID
) -> Optional[WritingSubmission]:
    """
    Find if a user has a pending draft submission for a prompt.
    """
    return (
        db.query(WritingSubmission)
        .filter(
            WritingSubmission.user_id == user_id,
            WritingSubmission.prompt_id == prompt_id,
            WritingSubmission.status == SubmissionStatus.PENDING,
        )
        .first()
    )


def save_draft(
    db: Session, user_id: uuid.UUID, prompt_id: uuid.UUID, content: str
) -> Tuple[WritingSubmission, WritingSubmissionVersion]:
    """
    Save or update a lightweight writing draft.
    """
    submission = get_pending_submission_by_prompt(db, user_id, prompt_id)

    if submission:
        # Update existing version 1 draft content
        version = (
            db.query(WritingSubmissionVersion)
            .filter(
                WritingSubmissionVersion.submission_id == submission.id,
                WritingSubmissionVersion.version_number == 1,
            )
            .first()
        )
        if version:
            version.text_content = content
        else:
            version = WritingSubmissionVersion(
                submission_id=submission.id,
                version_number=1,
                text_content=content,
            )
            db.add(version)
        db.commit()
        db.refresh(submission)
        db.refresh(version)
    else:
        # Create new submission with status PENDING (default for drafts)
        submission = WritingSubmission(
            user_id=user_id,
            prompt_id=prompt_id,
            status=SubmissionStatus.PENDING,
            revision_count=1,
        )
        db.add(submission)
        db.flush()  # Fetch submission.id

        version = WritingSubmissionVersion(
            submission_id=submission.id,
            version_number=1,
            text_content=content,
        )
        db.add(version)
        db.commit()
        db.refresh(submission)
        db.refresh(version)

    return submission, version


def submit_writing_essay(
    db: Session,
    user_id: uuid.UUID,
    prompt_id: uuid.UUID,
    content: str,
    word_count: int,
    time_spent_seconds: Optional[int] = None,
    daily_activity_id: Optional[uuid.UUID] = None,
) -> Tuple[WritingSubmission, WritingSubmissionVersion]:
    """
    Promote a draft to a processing submission, or create one directly in processing state.
    """
    submission = get_pending_submission_by_prompt(db, user_id, prompt_id)

    if submission:
        submission.status = SubmissionStatus.PROCESSING
        submission.word_count = word_count
        submission.time_spent_seconds = time_spent_seconds
        submission.daily_activity_id = daily_activity_id
        submission.submitted_at = datetime.now(timezone.utc)

        version = (
            db.query(WritingSubmissionVersion)
            .filter(
                WritingSubmissionVersion.submission_id == submission.id,
                WritingSubmissionVersion.version_number == 1,
            )
            .first()
        )
        if version:
            version.text_content = content
        else:
            version = WritingSubmissionVersion(
                submission_id=submission.id,
                version_number=1,
                text_content=content,
            )
            db.add(version)
        db.commit()
        db.refresh(submission)
        db.refresh(version)
    else:
        submission = WritingSubmission(
            user_id=user_id,
            prompt_id=prompt_id,
            status=SubmissionStatus.PROCESSING,
            revision_count=1,
            word_count=word_count,
            time_spent_seconds=time_spent_seconds,
            daily_activity_id=daily_activity_id,
            submitted_at=datetime.now(timezone.utc),
        )
        db.add(submission)
        db.flush()

        version = WritingSubmissionVersion(
            submission_id=submission.id,
            version_number=1,
            text_content=content,
        )
        db.add(version)
        db.commit()
        db.refresh(submission)
        db.refresh(version)

    return submission, version


def create_revision(
    db: Session,
    submission_id: uuid.UUID,
    content: str,
    word_count: int,
    time_spent_seconds: Optional[int] = None,
) -> Tuple[WritingSubmission, WritingSubmissionVersion]:
    """
    Create a new revision version on an existing submission, incrementing revision count.
    Max 3 revisions allowed (meaning version_number can go up to 4).
    """
    submission = db.query(WritingSubmission).filter(WritingSubmission.id == submission_id).first()
    if not submission:
        raise ValueError("Submission not found")

    if submission.revision_count >= 4:
        raise ValueError("Maximum revision limit reached")

    submission.revision_count += 1
    submission.status = SubmissionStatus.PROCESSING
    submission.word_count = word_count
    if time_spent_seconds is not None:
        submission.time_spent_seconds = time_spent_seconds
    submission.submitted_at = datetime.now(timezone.utc)

    version = WritingSubmissionVersion(
        submission_id=submission.id,
        version_number=submission.revision_count,
        text_content=content,
    )
    db.add(version)
    db.commit()
    db.refresh(submission)
    db.refresh(version)

    return submission, version


def update_evaluation_results(
    db: Session,
    submission_id: uuid.UUID,
    version_number: int,
    grammar_score: int,
    structure_score: int,
    vocabulary_score: int,
    coherence_score: int,
    overall_score: int,
    ai_feedback: dict,
    fixed_issues: Optional[dict] = None,
) -> Tuple[WritingSubmission, WritingSubmissionVersion]:
    """
    Update a submission and its version with the final AI evaluation scores and feedback details.
    """
    submission = db.query(WritingSubmission).filter(WritingSubmission.id == submission_id).first()
    if not submission:
        raise ValueError("Submission not found")

    version = (
        db.query(WritingSubmissionVersion)
        .filter(
            WritingSubmissionVersion.submission_id == submission_id,
            WritingSubmissionVersion.version_number == version_number,
        )
        .first()
    )
    if not version:
        raise ValueError("Version not found")

    # Update version details
    version.grammar_score = grammar_score
    version.structure_score = structure_score
    version.vocabulary_score = vocabulary_score
    version.coherence_score = coherence_score
    version.overall_score = overall_score
    version.ai_feedback = ai_feedback
    if fixed_issues is not None:
        version.fixed_issues = fixed_issues

    # Update overall parent submission values
    submission.grammar_score = grammar_score
    submission.structure_score = structure_score
    submission.vocabulary_score = vocabulary_score
    submission.coherence_score = coherence_score
    submission.overall_score = overall_score
    submission.status = SubmissionStatus.COMPLETED
    submission.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(submission)
    db.refresh(version)

    return submission, version


def get_user_portfolio(db: Session, user_id: uuid.UUID) -> List[WritingSubmission]:
    """
    Fetch all completed (or failed/processing) writing submissions for a user.
    """
    return (
        db.query(WritingSubmission)
        .filter(
            WritingSubmission.user_id == user_id,
            WritingSubmission.status != SubmissionStatus.PENDING,
        )
        .options(joinedload(WritingSubmission.versions))
        .order_by(WritingSubmission.submitted_at.desc())
        .all()
    )
