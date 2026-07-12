import logging
import uuid
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

from app.workers.celery_app import celery_app
from app.db.session import SessionLocal
from app.db.models.interview import InterviewPanelSession, PanelAgentFeedback
from app.db.models.enums import PanelSessionStatus, PanelAgentFeedbackType, OverallVerdict, InterviewMode
from app.services.gemini_client import generate_structured_response

logger = logging.getLogger(__name__)

def _generate_verdict(agent_type: str, state: Dict[str, Any], transcript_text: str) -> Dict[str, Any]:
    """Generates a verdict from a specific agent."""
    prompt = f"""
    You are the {agent_type} Interviewer on the panel.
    Review the full interview transcript for a {state['level']} level role in {state['domain']}.
    
    Transcript:
    {transcript_text}
    
    Provide your verdict (Strong Hire, Hire, Maybe, No Hire), a score contribution out of 100, and your verdict notes.
    """
    
    schema = {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["STRONG_HIRE", "HIRE", "MAYBE", "NO_HIRE"]},
            "score": {"type": "integer"},
            "notes": {"type": "string"}
        },
        "required": ["verdict", "score", "notes"]
    }
    
    try:
        return generate_structured_response(prompt, schema, temperature=0.2)
    except Exception as e:
        logger.error(f"Failed to generate {agent_type} verdict: {e}")
        return {"verdict": "MAYBE", "score": 50, "notes": "Failed to analyze."}

def _generate_supervisor_summary(verdicts: Dict[str, Any], transcript_text: str) -> Dict[str, Any]:
    """Generates the overall panel summary."""
    prompt = f"""
    You are the Panel Supervisor. You have received verdicts from your agents:
    {verdicts}
    
    Synthesize an overall final verdict and summary notes.
    """
    
    schema = {
        "type": "object",
        "properties": {
            "overall_verdict": {"type": "string", "enum": ["STRONG_HIRE", "HIRE", "MAYBE", "NO_HIRE"]},
            "summary_notes": {"type": "string"},
            "domain_score": {"type": "integer"},
            "communication_score": {"type": "integer"}
        },
        "required": ["overall_verdict", "summary_notes", "domain_score", "communication_score"]
    }
    
    try:
        return generate_structured_response(prompt, schema, temperature=0.3)
    except Exception as e:
        logger.error(f"Failed to generate supervisor summary: {e}")
        return {
            "overall_verdict": "MAYBE",
            "summary_notes": "Error aggregating verdicts.",
            "domain_score": 50,
            "communication_score": 50
        }

@celery_app.task(name="process_interview_report")
def process_interview_report(session_id: str):
    """
    Parallel post-session analysis task.
    """
    db = SessionLocal()
    try:
        session = db.query(InterviewPanelSession).filter(InterviewPanelSession.id == uuid.UUID(session_id)).first()
        if not session or session.status != PanelSessionStatus.ENDED:
            return
            
        state = session.session_state
        transcript_text = "\n".join([f"{t['speaker']}: {t['text']}" for t in state.get("transcript", [])])
        
        verdicts = {}
        agents_to_run = ["HR", "Technical", "Manager"]
        if session.interview_mode == InterviewMode.SINGLE_AGENT:
            agents_to_run = [session.selected_agent_type.value.capitalize()]
            
        # Run agents in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                agent: executor.submit(_generate_verdict, agent, state, transcript_text)
                for agent in agents_to_run
            }
            for agent, future in futures.items():
                verdicts[agent] = future.result()
                
                # Save individual agent feedback
                fb_type = getattr(PanelAgentFeedbackType, agent.upper())
                fb = PanelAgentFeedback(
                    session_id=session.id,
                    agent_type=fb_type,
                    score_contribution={"score": verdicts[agent]["score"], "verdict": verdicts[agent]["verdict"]},
                    verdict_notes=verdicts[agent]["notes"]
                )
                db.add(fb)
                
        # Run supervisor
        summary = _generate_supervisor_summary(verdicts, transcript_text)
        
        # Save summary feedback
        summary_fb = PanelAgentFeedback(
            session_id=session.id,
            agent_type=PanelAgentFeedbackType.SUMMARY,
            score_contribution={
                "domain_score": summary["domain_score"],
                "communication_score": summary["communication_score"]
            },
            verdict_notes=summary["summary_notes"]
        )
        db.add(summary_fb)
        
        # Update session overall verdict
        session.overall_verdict = getattr(OverallVerdict, summary["overall_verdict"])
        db.commit()
        
    except Exception as e:
        logger.error(f"Error processing interview report {session_id}: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()
