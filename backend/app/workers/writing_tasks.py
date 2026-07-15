import uuid
import logging
from app.workers.celery_app import celery_app
from app.db.session import SessionLocal
from app.db.models.writing import WritingPrompt, WritingSubmission, WritingSubmissionVersion
from app.db.models.enums import SubmissionStatus
from app.agents.writing.feedback_graph import feedback_graph
from app.agents.writing.revision_comparison_graph import revision_comparison_graph
from app.crud import writing as crud_writing
from app.middleware.rate_limit import refund_ai_rate_limit

logger = logging.getLogger("app.workers.writing_tasks")


@celery_app.task(
    name="app.workers.writing_tasks.process_writing_submission",
    acks_late=True,
    max_retries=3
)
def process_writing_submission(submission_id: str, version_id: str) -> None:
    """
    Task to evaluate a writing submission or revision.
    Invokes the multi-agent LangGraph pipeline, optionally performs
    revision comparison analysis, and saves the results back to the database.
    """
    logger.info(f"Processing writing submission {submission_id}, version {version_id}")
    db = SessionLocal()
    sub_uuid = None
    try:
        sub_uuid = uuid.UUID(submission_id)
        ver_uuid = uuid.UUID(version_id)

        submission = db.query(WritingSubmission).filter(WritingSubmission.id == sub_uuid).first()
        version = db.query(WritingSubmissionVersion).filter(WritingSubmissionVersion.id == ver_uuid).first()

        if not submission or not version:
            logger.error(f"Database records not found for submission_id={submission_id}, version_id={version_id}")
            return

        prompt = db.query(WritingPrompt).filter(WritingPrompt.id == submission.prompt_id).first()
        if not prompt:
            logger.error(f"Writing prompt not found for prompt_id={submission.prompt_id}")
            return

        # 1. Prepare initial graph state
        prompt_type_str = prompt.type.value if hasattr(prompt.type, "value") else str(prompt.type)
        state_input = {
            "text_content": version.text_content,
            "prompt_text": prompt.prompt_text,
            "prompt_type": prompt_type_str,
            "target_cefr_level": prompt.target_cefr_level,
            "grammar_report": None,
            "structure_report": None,
            "vocabulary_report": None,
            "coherence_report": None,
            "supervisor_report": None,
        }

        # 2. Execute multi-agent feedback pipeline
        final_state = feedback_graph.invoke(state_input)
        supervisor_report = final_state.get("supervisor_report", {})

        # 3. Consolidate full feedback JSON
        full_feedback = {
            "grammar": final_state.get("grammar_report"),
            "structure": final_state.get("structure_report"),
            "vocabulary": final_state.get("vocabulary_report"),
            "coherence": final_state.get("coherence_report"),
            "supervisor": supervisor_report,
        }

        # 4. Handle revision comparison if this is version > 1
        fixed_issues = None
        if version.version_number > 1:
            prev_version = (
                db.query(WritingSubmissionVersion)
                .filter(
                    WritingSubmissionVersion.submission_id == sub_uuid,
                    WritingSubmissionVersion.version_number == version.version_number - 1,
                )
                .first()
            )
            if prev_version and prev_version.ai_feedback:
                prev_issues = prev_version.ai_feedback.get("grammar", {}).get("issues", [])
                curr_issues = full_feedback.get("grammar", {}).get("issues", [])

                try:
                    comp_state = revision_comparison_graph.invoke({
                        "previous_issues": prev_issues,
                        "current_issues": curr_issues,
                        "fixed_issues": [],
                        "still_present_issues": [],
                        "new_issues_introduced": [],
                    })
                    fixed_issues = {
                        "fixed_issues": comp_state.get("fixed_issues", []),
                        "still_present_issues": comp_state.get("still_present_issues", []),
                        "new_issues_introduced": comp_state.get("new_issues_introduced", []),
                    }
                except Exception as e:
                    logger.error(f"Failed to run revision comparison: {e}")
                    fixed_issues = {
                        "fixed_issues": [],
                        "still_present_issues": [],
                        "new_issues_introduced": [],
                        "error": str(e),
                    }

        # 5. Save results to database using CRUD
        crud_writing.update_evaluation_results(
            db=db,
            submission_id=sub_uuid,
            version_number=version.version_number,
            grammar_score=supervisor_report.get("grammar_score", 70),
            structure_score=supervisor_report.get("structure_score", 70),
            vocabulary_score=supervisor_report.get("vocabulary_score", 70),
            coherence_score=supervisor_report.get("coherence_score", 70),
            overall_score=supervisor_report.get("overall_score", 70),
            ai_feedback=full_feedback,
            fixed_issues=fixed_issues,
        )
        logger.info(f"Successfully processed writing submission {submission_id}")

    except Exception as exc:
        logger.error(f"Error processing writing submission {submission_id}: {exc}", exc_info=True)
        # Attempt to set submission status to FAILED in case of crash
        if sub_uuid:
            try:
                db.rollback()
                submission = db.query(WritingSubmission).filter(WritingSubmission.id == sub_uuid).first()
                if submission:
                    submission.status = SubmissionStatus.FAILED
                    db.commit()
                    # Refund the quota on failure
                    refund_ai_rate_limit(str(submission.user_id))
            except Exception as db_exc:
                logger.error(f"Failed to fallback update submission to FAILED: {db_exc}")

    finally:
        db.close()
